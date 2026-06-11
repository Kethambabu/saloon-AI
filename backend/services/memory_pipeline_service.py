"""
Multi-Agent Memory Pipeline Service for SalonAI Workforce Platform.
Extracts raw database transactions, customer chats, and reviews, then synthesizes 
and indexes them hierarchically across 28 FAISS collections.
"""

import os
import logging
import datetime
from typing import Dict, Any, List, Optional
from datetime import timezone
from sqlalchemy import func
from sqlalchemy.orm import Session

from langchain_core.documents import Document

# Project imports
from db.models import (
    Appointment, Customer, Staff, Lead, Review, ChatLog, 
    CustomerRecommendation, BusinessMetricsHistory, AppointmentStatus,
    AgentMemory
)
from core.llm_config import get_llm_config
from core.openai_client_adapter import OpenAIChatCompletionClient
from autogen_core.models import SystemMessage, UserMessage
from rag.embeddings import get_embedding_model

logger = logging.getLogger(__name__)

# Default index directory
_DEFAULT_INDEX_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "faiss_indices",
)

AGENTS = ["receptionist", "customer", "staff", "lead", "upsell", "reputation", "business_intelligence"]
LEVELS = ["daily", "weekly", "monthly", "yearly"]


def _init_memory_directories() -> None:
    """Ensure all 28 directory paths exist."""
    for agent in AGENTS:
        for level in LEVELS:
            path = os.path.join(_DEFAULT_INDEX_DIR, agent, level)
            os.makedirs(path, exist_ok=True)


# Initialize directories immediately
_init_memory_directories()


class MemoryPipelineService:
    """
    Orchestrates daily data extraction, LLM narrative synthesis, and FAISS indexing.
    Also handles weekly, monthly, and yearly consolidation jobs.
    """

    def __init__(self):
        self.is_syncing = False
        llm_config = get_llm_config()
        config = llm_config.get_config()
        self.embedding_model = get_embedding_model()
        self.model_client = OpenAIChatCompletionClient(
            model=config["model"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            model_info=config["model_info"],
        )
        logger.info("[MemoryPipelineService] Initialized with centralized LLM client.")

    async def _generate_completion(self, system_prompt: str, user_content: str, max_tokens: int = 800) -> str:
        """Call LLM client to get text completion."""
        try:
            sys_msg = SystemMessage(content=system_prompt)
            user_msg = UserMessage(content=user_content, source="user")
            result = await self.model_client.create(
                messages=[sys_msg, user_msg], 
                max_tokens=max_tokens
            )
            return result.content.strip()
        except Exception as e:
            logger.error(f"[MemoryPipelineService] LLM Generation failed: {e}")
            return f"Failed to generate summary due to error: {e}"

    def _save_or_append_to_faiss(self, index_path: str, documents: List[Document]) -> None:
        """Helper to append documents to an existing FAISS index or create a new one."""
        from langchain_community.vectorstores import FAISS
        
        if not documents:
            return

        if os.path.exists(os.path.join(index_path, "index.faiss")):
            try:
                vectorstore = FAISS.load_local(
                    index_path, 
                    self.embedding_model, 
                    allow_dangerous_deserialization=True
                )
                vectorstore.add_documents(documents)
                vectorstore.save_local(index_path)
                logger.info(f"[MemoryPipelineService] Appended {len(documents)} docs to FAISS at {index_path}")
                return
            except Exception as e:
                logger.warning(f"[MemoryPipelineService] Failed to load existing index at {index_path}, recreating: {e}")

        vectorstore = FAISS.from_documents(documents, self.embedding_model)
        vectorstore.save_local(index_path)
        logger.info(f"[MemoryPipelineService] Created new FAISS index at {index_path} with {len(documents)} docs")

    def _load_faiss_documents(self, index_path: str, filter_dict: Optional[dict] = None) -> List[Document]:
        """Loads FAISS index and returns documents, optionally filtering by metadata."""
        from langchain_community.vectorstores import FAISS
        
        if not os.path.exists(os.path.join(index_path, "index.faiss")):
            return []

        try:
            vectorstore = FAISS.load_local(
                index_path, 
                self.embedding_model, 
                allow_dangerous_deserialization=True
            )
            docs = []
            for doc in vectorstore.docstore._dict.values():
                if filter_dict:
                    match = True
                    for k, v in filter_dict.items():
                        if doc.metadata.get(k) != v:
                            match = False
                            break
                    if match:
                        docs.append(doc)
                else:
                    docs.append(doc)
            return docs
        except Exception as e:
            logger.error(f"[MemoryPipelineService] Error loading FAISS docs at {index_path}: {e}")
            return []

    def _save_agent_memory(
        self,
        db: Session,
        agent_name: str,
        level: str,
        content: str,
        target_date: Optional[datetime.date] = None,
        target_year: Optional[int] = None,
        customer_id: Optional[Any] = None,
        staff_id: Optional[Any] = None
    ) -> None:
        """Helper to insert or update an agent memory record in PostgreSQL."""
        query = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == level
        )
        if target_date is not None:
            query = query.filter(AgentMemory.target_date == target_date)
        else:
            query = query.filter(AgentMemory.target_date.is_(None))
            
        if target_year is not None:
            query = query.filter(AgentMemory.target_year == target_year)
        else:
            query = query.filter(AgentMemory.target_year.is_(None))
            
        if customer_id is not None:
            query = query.filter(AgentMemory.customer_id == customer_id)
        else:
            query = query.filter(AgentMemory.customer_id.is_(None))
            
        if staff_id is not None:
            query = query.filter(AgentMemory.staff_id == staff_id)
        else:
            query = query.filter(AgentMemory.staff_id.is_(None))
            
        existing = query.first()
        if existing:
            existing.content = content
        else:
            new_mem = AgentMemory(
                agent_name=agent_name,
                level=level,
                target_date=target_date,
                target_year=target_year,
                customer_id=customer_id,
                staff_id=staff_id,
                content=content
            )
            db.add(new_mem)
        db.commit()

    def rebuild_agent_memory_index(self, db: Session, agent_name: str, level: str) -> None:
        """Clears the existing folder and rebuilds the FAISS index cleanly from all corresponding database records."""
        from langchain_core.documents import Document
        import shutil
        from langchain_community.vectorstores import FAISS

        # Query all memories for this agent and level
        memories = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == level
        ).all()

        documents = []
        for mem in memories:
            # Construct metadata
            metadata = {
                "agent": mem.agent_name,
                "level": mem.level,
            }
            if mem.target_date:
                date_str = mem.target_date.strftime("%Y-%m-%d")
                metadata["date"] = date_str
                # Add start_date / end_date / week / month for consolidations if applicable
                if mem.level == "weekly":
                    end_date = mem.target_date
                    start_date = end_date - datetime.timedelta(days=6)
                    metadata["start_date"] = start_date.strftime("%Y-%m-%d")
                    metadata["end_date"] = end_date.strftime("%Y-%m-%d")
                    metadata["week"] = f"Week-{start_date.strftime('%Y-W%W')}"
                elif mem.level == "monthly":
                    end_date = mem.target_date
                    start_date = end_date - datetime.timedelta(days=29)
                    metadata["start_date"] = start_date.strftime("%Y-%m-%d")
                    metadata["end_date"] = end_date.strftime("%Y-%m-%d")
                    metadata["month"] = start_date.strftime("%Y-%m")
            if mem.target_year:
                metadata["year"] = mem.target_year
                if mem.level == "yearly":
                    start_date = datetime.date(mem.target_year, 1, 1)
                    end_date = datetime.date(mem.target_year, 12, 31)
                    metadata["start_date"] = start_date.strftime("%Y-%m-%d")
                    metadata["end_date"] = end_date.strftime("%Y-%m-%d")

            if mem.customer_id:
                metadata["customer_id"] = str(mem.customer_id)
            if mem.staff_id:
                metadata["staff_id"] = str(mem.staff_id)

            # Query the name of the entity if customer_id or staff_id is set
            entity_name = "Unknown"
            if mem.customer_id:
                cust = db.query(Customer).filter(Customer.id == mem.customer_id).first()
                if cust:
                    entity_name = cust.full_name
            elif mem.staff_id:
                stf = db.query(Staff).filter(Staff.id == mem.staff_id).first()
                if stf:
                    entity_name = f"{stf.first_name} {stf.last_name}"

            # Build page_content depending on agent and level
            page_content = ""
            if mem.level == "daily":
                date_str = mem.target_date.strftime("%Y-%m-%d") if mem.target_date else ""
                if mem.agent_name == "receptionist":
                    page_content = f"Date: {date_str}\n\nReception Summary:\n{mem.content}"
                elif mem.agent_name == "customer":
                    page_content = f"Date: {date_str}\nCustomer: {entity_name}\nProfile Summary:\n{mem.content}"
                elif mem.agent_name == "staff":
                    page_content = f"Date: {date_str}\nStaff member: {entity_name}\nPerformance Summary:\n{mem.content}"
                elif mem.agent_name == "lead":
                    page_content = f"Date: {date_str}\n\nLead Follow-up Summary:\n{mem.content}"
                elif mem.agent_name == "upsell":
                    page_content = f"Date: {date_str}\n\nUpsell Strategy Summary:\n{mem.content}"
                elif mem.agent_name == "reputation":
                    page_content = f"Date: {date_str}\n\nReputation & Review Summary:\n{mem.content}"
                elif mem.agent_name == "business_intelligence":
                    page_content = f"Date: {date_str}\n\nDaily Business Intelligence Snapshot:\n{mem.content}"
                else:
                    page_content = f"Date: {date_str}\n\nSummary:\n{mem.content}"
            elif mem.level == "weekly":
                end_date_str = mem.target_date.strftime("%Y-%m-%d") if mem.target_date else ""
                start_date_str = (mem.target_date - datetime.timedelta(days=6)).strftime("%Y-%m-%d") if mem.target_date else ""
                if mem.agent_name in ["customer", "staff"]:
                    page_content = (
                        f"Week: {start_date_str} to {end_date_str}\n"
                        f"Entity: {entity_name} ({mem.customer_id or mem.staff_id})\n\n"
                        f"Weekly Aggregated Summary:\n{mem.content}"
                    )
                else:
                    page_content = f"Week: {start_date_str} to {end_date_str}\n\nWeekly Aggregated Summary:\n{mem.content}"
            elif mem.level == "monthly":
                end_date_str = mem.target_date.strftime("%Y-%m-%d") if mem.target_date else ""
                start_date_str = (mem.target_date - datetime.timedelta(days=29)).strftime("%Y-%m-%d") if mem.target_date else ""
                if mem.agent_name in ["customer", "staff"]:
                    page_content = (
                        f"Month: {mem.target_date.strftime('%B %Y') if mem.target_date else ''}\n"
                        f"Entity: {entity_name} ({mem.customer_id or mem.staff_id})\n\n"
                        f"Monthly Aggregated Summary:\n{mem.content}"
                    )
                else:
                    page_content = f"Month: {mem.target_date.strftime('%B %Y') if mem.target_date else ''}\n\nMonthly Aggregated Summary:\n{mem.content}"
            elif mem.level == "yearly":
                if mem.agent_name in ["customer", "staff"]:
                    page_content = (
                        f"Year: {mem.target_year}\n"
                        f"Entity: {entity_name} ({mem.customer_id or mem.staff_id})\n\n"
                        f"Yearly Aggregated Summary:\n{mem.content}"
                    )
                else:
                    page_content = f"Year: {mem.target_year}\n\nYearly Aggregated Summary:\n{mem.content}"

            documents.append(Document(page_content=page_content, metadata=metadata))

        index_path = os.path.join(_DEFAULT_INDEX_DIR, agent_name, level)
        if os.path.exists(index_path):
            try:
                shutil.rmtree(index_path)
            except Exception as e:
                logger.warning(f"Could not delete index directory {index_path}: {e}")
        os.makedirs(index_path, exist_ok=True)

        if documents:
            vectorstore = FAISS.from_documents(documents, self.embedding_model)
            vectorstore.save_local(index_path)
            logger.info(f"[MemoryPipelineService] Rebuilt FAISS index at {index_path} with {len(documents)} docs")
        else:
            logger.info(f"[MemoryPipelineService] Rebuilt FAISS index at {index_path} is empty (no DB records)")

    # =========================================================================
    async def run_daily_pipeline(self, db: Session, target_date: Optional[datetime.date] = None, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        """Runs the complete daily pipeline to extract data for target_date and build daily summaries."""
        if target_date is None:
            target_date = datetime.date.today()

        logger.info(f"[MemoryPipelineService] Starting daily pipeline for date: {target_date} (agent: {agent_name or 'all'})")
        
        # Define boundaries for queries
        day_start = datetime.datetime.combine(target_date, datetime.time.min).replace(tzinfo=None)
        day_end = datetime.datetime.combine(target_date, datetime.time.max).replace(tzinfo=None)
        date_str = target_date.strftime("%Y-%m-%d")

        # Extract primary data batches
        appts = db.query(Appointment).filter(Appointment.start_time >= day_start, Appointment.start_time < day_end).all()
        chat_logs = db.query(ChatLog).filter(ChatLog.created_at >= day_start, ChatLog.created_at < day_end).all()
        reviews = db.query(Review).filter(Review.created_at >= day_start, Review.created_at < day_end).all()
        leads = db.query(Lead).filter(Lead.created_at >= day_start, Lead.created_at < day_end).all()
        upsells = db.query(CustomerRecommendation).filter(CustomerRecommendation.created_at >= day_start, CustomerRecommendation.created_at < day_end).all()

        results = {}

        # 1. RECEPTIONIST DAILY MEMORY
        if not agent_name or agent_name == "receptionist":
            results["receptionist"] = await self._ingest_receptionist_daily(db, target_date, date_str, appts, chat_logs)

        # 2. CUSTOMER DAILY MEMORIES (isolation by customer_id)
        if not agent_name or agent_name == "customer":
            results["customer"] = await self._ingest_customer_daily(db, target_date, date_str, appts, chat_logs, reviews)

        # 3. STAFF DAILY MEMORIES (isolation by staff_id)
        if not agent_name or agent_name == "staff":
            results["staff"] = await self._ingest_staff_daily(db, target_date, date_str, appts, reviews)

        # 4. LEAD DAILY MEMORY
        if not agent_name or agent_name == "lead":
            results["lead"] = await self._ingest_lead_daily(db, target_date, date_str, leads)

        # 5. UPSELL DAILY MEMORY
        if not agent_name or agent_name == "upsell":
            results["upsell"] = await self._ingest_upsell_daily(db, target_date, date_str, upsells)

        # 6. REPUTATION DAILY MEMORY
        if not agent_name or agent_name == "reputation":
            results["reputation"] = await self._ingest_reputation_daily(db, target_date, date_str, reviews)

        # 7. BUSINESS INTELLIGENCE DAILY MEMORY
        if not agent_name or agent_name == "business_intelligence":
            results["business_intelligence"] = await self._ingest_bi_daily(db, target_date, date_str)

        if rebuild_index:
            for agent in results.keys():
                if results[agent] > 0:
                    self.rebuild_agent_memory_index(db, agent, "daily")

        logger.info(f"[MemoryPipelineService] Daily pipeline completed for {target_date} (agent: {agent_name or 'all'})")
        return results

    # --- Agent Summarization Ingestion Core Routines ---

    async def _ingest_receptionist_daily(self, db: Session, target_date: datetime.date, date_str: str, appts: List[Appointment], chat_logs: List[ChatLog]) -> int:
        booked = len(appts)
        cancelled = sum(1 for a in appts if a.status == AppointmentStatus.CANCELLED)
        rescheduled = sum(1 for a in appts if a.notes and "rescheduled" in a.notes.lower())
        
        cust_queries = [c.message for c in chat_logs if c.sender == "user" and c.agent_type == "RECEPTIONIST"]
        
        sys_prompt = "You are Clara, the Head Salon Receptionist. Summarize today's receptionist activities into a clean narrative report."
        user_content = (
            f"Date: {date_str}\n"
            f"Appointments Booked: {booked}\n"
            f"Appointments Cancelled: {cancelled}\n"
            f"Appointments Rescheduled: {rescheduled}\n"
            f"Customer Questions Today:\n" + "\n".join(f"- {q}" for q in cust_queries[:15])
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name="receptionist",
            level="daily",
            content=summary,
            target_date=target_date
        )
        return 1

    async def _ingest_customer_daily(self, db: Session, target_date: datetime.date, date_str: str, appts: List[Appointment], chat_logs: List[ChatLog], reviews: List[Review]) -> int:
        # Get active customer IDs
        appt_custs = {a.customer_id for a in appts if a.customer_id}
        chat_custs = {c.customer_id for c in chat_logs if c.customer_id}
        review_custs = {r.customer_id for r in reviews if r.customer_id}
        active_ids = appt_custs.union(chat_custs).union(review_custs)
        
        count = 0
        for cust_id in active_ids:
            customer = db.query(Customer).filter(Customer.id == cust_id).first()
            if not customer:
                continue
            
            c_appts = [a for a in appts if a.customer_id == cust_id]
            c_chats = [c for c in chat_logs if c.customer_id == cust_id]
            c_reviews = [r for r in reviews if r.customer_id == cust_id]
            
            services = ", ".join(a.service.name for a in c_appts if a.service)
            stylist = ", ".join(f"{a.staff.first_name} {a.staff.last_name}" for a in c_appts if a.staff)
            spend = sum(float(a.service.price) for a in c_appts if a.service and a.status == AppointmentStatus.COMPLETED)
            
            sys_prompt = "You are a customer memory compiler. Synthesize the customer's daily profile and preferences."
            user_content = (
                f"Customer: {customer.full_name}\n"
                f"Completed Services today: {services}\n"
                f"Stylists chosen today: {stylist}\n"
                f"Total spend today: ₹{spend}\n"
                f"Chat logs content: " + " | ".join(c.message for c in c_chats[:5]) + "\n"
                f"Reviews comments: " + " | ".join(r.comment for r in c_reviews if r.comment)
            )
            
            summary = await self._generate_completion(sys_prompt, user_content, max_tokens=400)
            self._save_agent_memory(
                db=db,
                agent_name="customer",
                level="daily",
                content=summary,
                target_date=target_date,
                customer_id=cust_id
            )
            count += 1
            
        return count

    async def _ingest_staff_daily(self, db: Session, target_date: datetime.date, date_str: str, appts: List[Appointment], reviews: List[Review]) -> int:
        # Get active staff IDs
        active_ids = {a.staff_id for a in appts if a.staff_id}
        
        count = 0
        for staff_id in active_ids:
            staff = db.query(Staff).filter(Staff.id == staff_id).first()
            if not staff:
                continue
            
            s_appts = [a for a in appts if a.staff_id == staff_id]
            completed = sum(1 for a in s_appts if a.status == AppointmentStatus.COMPLETED)
            revenue = sum(float(a.service.price) for a in s_appts if a.service and a.status == AppointmentStatus.COMPLETED)
            
            # Fetch reviews for these appointments
            appt_ids = {a.id for a in s_appts}
            s_reviews = [r for r in reviews if r.appointment_id in appt_ids]
            avg_rating = sum(r.rating for r in s_reviews) / len(s_reviews) if s_reviews else 0.0
            
            sys_prompt = "You are a staff performance memory aggregator. Summarize the staff productivity for today."
            user_content = (
                f"Staff Stylist: {staff.first_name} {staff.last_name}\n"
                f"Appointments completed: {completed}\n"
                f"Revenue generated today: ₹{revenue}\n"
                f"Average Rating today: {avg_rating:.1f}/5.0\n"
                f"Customer Review Comments: " + " | ".join(r.comment for r in s_reviews if r.comment)
            )
            
            summary = await self._generate_completion(sys_prompt, user_content, max_tokens=400)
            self._save_agent_memory(
                db=db,
                agent_name="staff",
                level="daily",
                content=summary,
                target_date=target_date,
                staff_id=staff_id
            )
            count += 1
            
        return count

    async def _ingest_lead_daily(self, db: Session, target_date: datetime.date, date_str: str, leads: List[Lead]) -> int:
        new_leads = len(leads)
        converted = sum(1 for l in leads if l.status.value == "CONVERTED" or l.status == "CONVERTED")
        lost = sum(1 for l in leads if l.status.value == "LOST" or l.status == "LOST")
        
        sys_prompt = "You are Mia, the CRM Lead Follow-up Specialist. Summarize today's lead activity stats and updates."
        user_content = (
            f"Date: {date_str}\n"
            f"New Leads Ingested: {new_leads}\n"
            f"Leads Converted: {converted}\n"
            f"Leads Marked Lost: {lost}\n"
            f"Leads details:\n" + "\n".join(f"- Name: {l.customer_name} | Source: {l.source} | Notes: {l.notes}" for l in leads[:10])
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name="lead",
            level="daily",
            content=summary,
            target_date=target_date
        )
        return 1

    async def _ingest_upsell_daily(self, db: Session, target_date: datetime.date, date_str: str, upsells: List[CustomerRecommendation]) -> int:
        total = len(upsells)
        accepted = sum(1 for u in upsells if u.accepted)
        rate = (accepted / total * 100.0) if total > 0 else 0.0
        revenue = sum(float(u.recommended_service.price) for u in upsells if u.accepted and u.recommended_service)
        
        sys_prompt = "You are Max, the Upsell & Cross-Sell Strategist. Summarize today's upsell performance aggregates."
        user_content = (
            f"Date: {date_str}\n"
            f"Upsell Offers Made: {total}\n"
            f"Offers Accepted: {accepted}\n"
            f"Acceptance Rate: {rate:.1f}%\n"
            f"Upsell Revenue Generated: ₹{revenue}\n"
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name="upsell",
            level="daily",
            content=summary,
            target_date=target_date
        )
        return 1

    async def _ingest_reputation_daily(self, db: Session, target_date: datetime.date, date_str: str, reviews: List[Review]) -> int:
        total = len(reviews)
        avg_rating = sum(r.rating for r in reviews) / total if total > 0 else 0.0
        pos = sum(1 for r in reviews if r.rating >= 4)
        neg = sum(1 for r in reviews if r.rating <= 2)
        
        sys_prompt = "You are Olivia, the Reputation & Reviews Coordinator. Summarize customer sentiments and ratings today."
        user_content = (
            f"Date: {date_str}\n"
            f"New Reviews Received: {total}\n"
            f"Average Rating: {avg_rating:.1f}/5.0\n"
            f"Positive Reviews count: {pos}\n"
            f"Critical/Negative Reviews count: {neg}\n"
            f"Comments posted today:\n" + "\n".join(f"- {r.rating}★: {r.comment}" for r in reviews if r.comment)
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name="reputation",
            level="daily",
            content=summary,
            target_date=target_date
        )
        return 1

    async def _ingest_bi_daily(self, db: Session, target_date: datetime.date, date_str: str) -> int:
        snap = db.query(BusinessMetricsHistory).filter(BusinessMetricsHistory.metric_date == target_date).first()
        
        revenue = float(snap.revenue) if snap else 0.0
        bookings = snap.appointments if snap else 0
        conv = float(snap.lead_conversion) if snap else 0.0
        rating = float(snap.average_rating) if snap else 0.0
        upsell = float(snap.upsell_revenue) if snap else 0.0
        top_svc = snap.top_service if snap else "Precision Haircut"
        top_stf = snap.top_staff if snap else "Priya Sharma"
        
        sys_prompt = "You are Atlas, the Business Intelligence Analyst. Generate a corporate business narrative based on daily metrics."
        user_content = (
            f"Date: {date_str}\n"
            f"Total Business Revenue: ₹{revenue:,.2f}\n"
            f"Bookings Completed: {bookings}\n"
            f"Lead Conversion Rate: {conv * 100.0:.1f}%\n"
            f"Average Stylist Rating: {rating:.1f}★\n"
            f"Upsell Yield: ₹{upsell:,.2f}\n"
            f"Top Service Segment: {top_svc}\n"
            f"Top Staff Performer: {top_stf}"
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name="business_intelligence",
            level="daily",
            content=summary,
            target_date=target_date
        )
        return 1

    # =========================================================================
    # WEEKLY CONSOLIDATION PIPELINE (7 Daily -> 1 Weekly)
    # =========================================================================
    async def run_weekly_pipeline(self, db: Session, end_date: datetime.date, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        """Consolidates daily summaries from the past 7 days into weekly memories."""
        logger.info(f"[MemoryPipelineService] Starting weekly consolidation pipeline ending: {end_date} (agent: {agent_name or 'all'})")
        start_date = end_date - datetime.timedelta(days=6)
        
        results = {}
        for agent in AGENTS:
            if agent_name and agent != agent_name:
                continue
            if agent in ["customer", "staff"]:
                results[agent] = await self._consolidate_weekly_isolated(db, agent, start_date, end_date)
            else:
                results[agent] = await self._consolidate_weekly_general(db, agent, start_date, end_date)
                
        if rebuild_index:
            for agent in results.keys():
                if results[agent] > 0:
                    self.rebuild_agent_memory_index(db, agent, "weekly")

        return results

    async def _consolidate_weekly_general(self, db: Session, agent_name: str, start_date: datetime.date, end_date: datetime.date) -> int:
        daily_mems = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == "daily",
            AgentMemory.target_date >= start_date,
            AgentMemory.target_date <= end_date
        ).all()
        
        if not daily_mems:
            logger.info(f"No daily DB memories found for {agent_name} in week {start_date} to {end_date}")
            return 0
            
        sys_prompt = f"You are the memory manager consolidating the weekly memory ledger for agent: {agent_name}."
        user_content = (
            f"Consolidation Week: {start_date} to {end_date}\n\n"
            "Daily logs collected:\n" + "\n\n".join(f"Date: {mem.target_date}\nSummary: {mem.content}" for mem in daily_mems)
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name=agent_name,
            level="weekly",
            content=summary,
            target_date=end_date
        )
        return 1

    async def _consolidate_weekly_isolated(self, db: Session, agent_name: str, start_date: datetime.date, end_date: datetime.date) -> int:
        daily_mems = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == "daily",
            AgentMemory.target_date >= start_date,
            AgentMemory.target_date <= end_date
        ).all()
        
        entity_key = "customer_id" if agent_name == "customer" else "staff_id"
        grouped_mems = {}
        for mem in daily_mems:
            ent_id = getattr(mem, entity_key)
            if ent_id:
                if ent_id not in grouped_mems:
                    grouped_mems[ent_id] = []
                grouped_mems[ent_id].append(mem)
                
        count = 0
        for ent_id, mems in grouped_mems.items():
            name = "Unknown"
            if agent_name == "customer":
                customer = db.query(Customer).filter(Customer.id == ent_id).first()
                name = customer.full_name if customer else "Customer"
            elif agent_name == "staff":
                staff = db.query(Staff).filter(Staff.id == ent_id).first()
                name = f"{staff.first_name} {staff.last_name}" if staff else "Staff"
                
            sys_prompt = f"You are the memory manager consolidating the weekly memory ledger for {agent_name}: {name}."
            user_content = (
                f"Consolidation Week: {start_date} to {end_date}\n\n"
                f"Daily profiles collected:\n" + "\n\n".join(f"Date: {mem.target_date}\nSummary: {mem.content}" for mem in mems)
            )
            
            summary = await self._generate_completion(sys_prompt, user_content, max_tokens=500)
            self._save_agent_memory(
                db=db,
                agent_name=agent_name,
                level="weekly",
                content=summary,
                target_date=end_date,
                customer_id=ent_id if agent_name == "customer" else None,
                staff_id=ent_id if agent_name == "staff" else None
            )
            count += 1
            
        return count

    # =========================================================================
    # MONTHLY CONSOLIDATION PIPELINE (4 Weekly -> 1 Monthly)
    # =========================================================================
    async def run_monthly_pipeline(self, db: Session, end_date: datetime.date, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        """Consolidates weekly summaries from the past month into monthly memories."""
        logger.info(f"[MemoryPipelineService] Starting monthly consolidation pipeline ending: {end_date} (agent: {agent_name or 'all'})")
        start_date = end_date - datetime.timedelta(days=29)
        
        results = {}
        for agent in AGENTS:
            if agent_name and agent != agent_name:
                continue
            if agent in ["customer", "staff"]:
                results[agent] = await self._consolidate_monthly_isolated(db, agent, start_date, end_date)
            else:
                results[agent] = await self._consolidate_monthly_general(db, agent, start_date, end_date)
                
        if rebuild_index:
            for agent in results.keys():
                if results[agent] > 0:
                    self.rebuild_agent_memory_index(db, agent, "monthly")

        return results

    async def _consolidate_monthly_general(self, db: Session, agent_name: str, start_date: datetime.date, end_date: datetime.date) -> int:
        weekly_mems = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == "weekly",
            AgentMemory.target_date >= start_date,
            AgentMemory.target_date <= end_date
        ).all()
        
        if not weekly_mems:
            logger.info(f"No weekly DB memories found for {agent_name} in month {start_date} to {end_date}")
            return 0
            
        sys_prompt = f"You are the memory manager consolidating the monthly memory ledger for agent: {agent_name}."
        user_content = (
            f"Consolidation Month: {start_date.strftime('%B %Y')}\n\n"
            "Weekly logs collected:\n" + "\n\n".join(f"Week Ending: {mem.target_date}\nSummary: {mem.content}" for mem in weekly_mems)
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name=agent_name,
            level="monthly",
            content=summary,
            target_date=end_date
        )
        return 1

    async def _consolidate_monthly_isolated(self, db: Session, agent_name: str, start_date: datetime.date, end_date: datetime.date) -> int:
        weekly_mems = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == "weekly",
            AgentMemory.target_date >= start_date,
            AgentMemory.target_date <= end_date
        ).all()
        
        entity_key = "customer_id" if agent_name == "customer" else "staff_id"
        grouped_mems = {}
        for mem in weekly_mems:
            ent_id = getattr(mem, entity_key)
            if ent_id:
                if ent_id not in grouped_mems:
                    grouped_mems[ent_id] = []
                grouped_mems[ent_id].append(mem)
                
        count = 0
        for ent_id, mems in grouped_mems.items():
            name = "Unknown"
            if agent_name == "customer":
                customer = db.query(Customer).filter(Customer.id == ent_id).first()
                name = customer.full_name if customer else "Customer"
            elif agent_name == "staff":
                staff = db.query(Staff).filter(Staff.id == ent_id).first()
                name = f"{staff.first_name} {staff.last_name}" if staff else "Staff"
                
            sys_prompt = f"You are the memory manager consolidating the monthly memory ledger for {agent_name}: {name}."
            user_content = (
                f"Consolidation Month: {start_date.strftime('%B %Y')}\n\n"
                f"Weekly profiles collected:\n" + "\n\n".join(f"Week Ending: {mem.target_date}\nSummary: {mem.content}" for mem in mems)
            )
            
            summary = await self._generate_completion(sys_prompt, user_content, max_tokens=500)
            self._save_agent_memory(
                db=db,
                agent_name=agent_name,
                level="monthly",
                content=summary,
                target_date=end_date,
                customer_id=ent_id if agent_name == "customer" else None,
                staff_id=ent_id if agent_name == "staff" else None
            )
            count += 1
            
        return count

    # =========================================================================
    # YEARLY CONSOLIDATION PIPELINE (12 Monthly -> 1 Yearly)
    # =========================================================================
    async def run_yearly_pipeline(self, db: Session, year: int, agent_name: Optional[str] = None, rebuild_index: bool = True) -> Dict[str, Any]:
        """Consolidates monthly summaries from the specified year into yearly memories."""
        logger.info(f"[MemoryPipelineService] Starting yearly consolidation pipeline for year: {year} (agent: {agent_name or 'all'})")
        start_date = datetime.date(year, 1, 1)
        end_date = datetime.date(year, 12, 31)
        
        results = {}
        for agent in AGENTS:
            if agent_name and agent != agent_name:
                continue
            if agent in ["customer", "staff"]:
                results[agent] = await self._consolidate_yearly_isolated(db, agent, start_date, end_date, year)
            else:
                results[agent] = await self._consolidate_yearly_general(db, agent, start_date, end_date, year)
                
        if rebuild_index:
            for agent in results.keys():
                if results[agent] > 0:
                    self.rebuild_agent_memory_index(db, agent, "yearly")

        return results

    async def _consolidate_yearly_general(self, db: Session, agent_name: str, start_date: datetime.date, end_date: datetime.date, year: int) -> int:
        monthly_mems = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == "monthly",
            AgentMemory.target_date >= start_date,
            AgentMemory.target_date <= end_date
        ).all()
        
        if not monthly_mems:
            logger.info(f"No monthly DB memories found for {agent_name} in year {year}")
            return 0
            
        sys_prompt = f"You are the memory manager consolidating the yearly memory ledger for agent: {agent_name}."
        user_content = (
            f"Consolidation Year: {year}\n\n"
            "Monthly logs collected:\n" + "\n\n".join(f"Month Ending: {mem.target_date}\nSummary: {mem.content}" for mem in monthly_mems)
        )
        
        summary = await self._generate_completion(sys_prompt, user_content)
        self._save_agent_memory(
            db=db,
            agent_name=agent_name,
            level="yearly",
            content=summary,
            target_year=year
        )
        return 1

    async def _consolidate_yearly_isolated(self, db: Session, agent_name: str, start_date: datetime.date, end_date: datetime.date, year: int) -> int:
        monthly_mems = db.query(AgentMemory).filter(
            AgentMemory.agent_name == agent_name,
            AgentMemory.level == "monthly",
            AgentMemory.target_date >= start_date,
            AgentMemory.target_date <= end_date
        ).all()
        
        entity_key = "customer_id" if agent_name == "customer" else "staff_id"
        grouped_mems = {}
        for mem in monthly_mems:
            ent_id = getattr(mem, entity_key)
            if ent_id:
                if ent_id not in grouped_mems:
                    grouped_mems[ent_id] = []
                grouped_mems[ent_id].append(mem)
                
        count = 0
        for ent_id, mems in grouped_mems.items():
            name = "Unknown"
            if agent_name == "customer":
                customer = db.query(Customer).filter(Customer.id == ent_id).first()
                name = customer.full_name if customer else "Customer"
            elif agent_name == "staff":
                staff = db.query(Staff).filter(Staff.id == ent_id).first()
                name = f"{staff.first_name} {staff.last_name}" if staff else "Staff"
                
            sys_prompt = f"You are the memory manager consolidating the yearly memory ledger for {agent_name}: {name}."
            user_content = (
                f"Consolidation Year: {year}\n\n"
                f"Monthly profiles collected:\n" + "\n\n".join(f"Month Ending: {mem.target_date}\nSummary: {mem.content}" for mem in mems)
            )
            
            summary = await self._generate_completion(sys_prompt, user_content, max_tokens=500)
            self._save_agent_memory(
                db=db,
                agent_name=agent_name,
                level="yearly",
                content=summary,
                target_year=year,
                customer_id=ent_id if agent_name == "customer" else None,
                staff_id=ent_id if agent_name == "staff" else None
            )
            count += 1
            
        return count

    def get_sync_status(self, db: Session) -> Dict[str, Any]:
        """Calculates sync start/end boundaries based on DB records and last_rag_run.json."""
        import json
        import os
        from sqlalchemy import func
        from db.models import Appointment, ChatLog, Lead

        data_dir = os.path.dirname(_DEFAULT_INDEX_DIR)
        state_file = os.path.join(data_dir, "last_rag_run.json")

        last_run_date_str = None
        if os.path.exists(state_file):
            try:
                with open(state_file, "r") as f:
                    state_data = json.load(f)
                    last_run_date_str = state_data.get("last_run_date")
            except Exception as e:
                logger.warning(f"Failed to read last_rag_run.json: {e}")

        # Find earliest record in DB
        earliest_date = None
        try:
            min_appt = db.query(func.min(Appointment.start_time)).scalar()
            min_chat = db.query(func.min(ChatLog.created_at)).scalar()
            min_lead = db.query(func.min(Lead.created_at)).scalar()

            dates = []
            if min_appt:
                dates.append(min_appt.date() if isinstance(min_appt, datetime.datetime) else min_appt)
            if min_chat:
                dates.append(min_chat.date() if isinstance(min_chat, datetime.datetime) else min_chat)
            if min_lead:
                dates.append(min_lead.date() if isinstance(min_lead, datetime.datetime) else min_lead)

            if dates:
                earliest_date = min(dates)
        except Exception as e:
            logger.error(f"Failed to query earliest record date: {e}")

        if earliest_date is None:
            earliest_date = datetime.date(2026, 6, 1)

        # Set start_date
        if last_run_date_str:
            try:
                last_run_date = datetime.datetime.strptime(last_run_date_str, "%Y-%m-%d").date()
                start_date = last_run_date + datetime.timedelta(days=1)
            except ValueError:
                start_date = earliest_date
        else:
            start_date = earliest_date

        # Set end_date (yesterday)
        today = datetime.date.today()
        end_date = today - datetime.timedelta(days=1)

        sync_available = start_date <= end_date

        return {
            "last_run_date": last_run_date_str,
            "earliest_date": earliest_date.strftime("%Y-%m-%d"),
            "next_sync_start": start_date.strftime("%Y-%m-%d"),
            "next_sync_end": end_date.strftime("%Y-%m-%d"),
            "sync_available": sync_available,
            "is_syncing": getattr(self, "is_syncing", False)
        }

    async def run_unified_sync(self, db: Session) -> Dict[str, Any]:
        """Runs the unified sync loops day-by-day and rebuilds FAISS indexes once at the end."""
        import json
        import os
        from rag.ingest import RAGIngestor

        status = self.get_sync_status(db)
        if not status["sync_available"]:
            return {
                "success": True,
                "action": "skipped",
                "message": "Vector database is already up to date.",
                "details": status
            }

        self.is_syncing = True
        try:
            start_date = datetime.datetime.strptime(status["next_sync_start"], "%Y-%m-%d").date()
            end_date = datetime.datetime.strptime(status["next_sync_end"], "%Y-%m-%d").date()

            logger.info(f"[MemoryPipelineService] Starting unified synchronization from {start_date} to {end_date}")

            touched_daily = False
            touched_weekly = False
            touched_monthly = False
            touched_yearly = False

            current_date = start_date
            delta = datetime.timedelta(days=1)

            while current_date <= end_date:
                # 1. Run daily pipeline without rebuilding FAISS index immediately
                logger.info(f"[MemoryPipelineService] Unified Sync: Processing Daily summaries for {current_date}")
                await self.run_daily_pipeline(db, target_date=current_date, rebuild_index=False)
                touched_daily = True

                # 2. Run weekly consolidation if Sunday
                if current_date.weekday() == 6:
                    logger.info(f"[MemoryPipelineService] Unified Sync: Processing Weekly summaries ending {current_date}")
                    await self.run_weekly_pipeline(db, end_date=current_date, rebuild_index=False)
                    touched_weekly = True

                # 3. Run monthly consolidation if last day of calendar month
                if (current_date + delta).month != current_date.month:
                    logger.info(f"[MemoryPipelineService] Unified Sync: Processing Monthly summaries ending {current_date}")
                    await self.run_monthly_pipeline(db, end_date=current_date, rebuild_index=False)
                    touched_monthly = True

                # 4. Run yearly consolidation if Dec 31
                if current_date.month == 12 and current_date.day == 31:
                    logger.info(f"[MemoryPipelineService] Unified Sync: Processing Yearly summaries for year {current_date.year}")
                    await self.run_yearly_pipeline(db, year=current_date.year, rebuild_index=False)
                    touched_yearly = True

                current_date += delta

            # Rebuild FAISS indexes for all touched levels
            logger.info("[MemoryPipelineService] Rebuilding FAISS indices for all agents...")
            for agent in AGENTS:
                if touched_daily:
                    self.rebuild_agent_memory_index(db, agent, "daily")
                if touched_weekly:
                    self.rebuild_agent_memory_index(db, agent, "weekly")
                if touched_monthly:
                    self.rebuild_agent_memory_index(db, agent, "monthly")
                if touched_yearly:
                    self.rebuild_agent_memory_index(db, agent, "yearly")

            # Ingest/rebuild customer interactions RAG index
            logger.info("[MemoryPipelineService] Rebuilding customer interactions RAG index...")
            try:
                ingestor = RAGIngestor()
                ingestor.ingest_interactions(force_rebuild=True)
            except Exception as e:
                logger.error(f"Failed to rebuild customer interactions index: {e}")

            # Update last run state
            data_dir = os.path.dirname(_DEFAULT_INDEX_DIR)
            state_file = os.path.join(data_dir, "last_rag_run.json")
            try:
                with open(state_file, "w") as f:
                    json.dump({"last_run_date": end_date.strftime("%Y-%m-%d")}, f)
            except Exception as e:
                logger.error(f"Failed to write last_rag_run.json: {e}")

            logger.info(f"[MemoryPipelineService] Unified synchronization complete up to {end_date}")

            return {
                "success": True,
                "action": "synchronized",
                "message": f"Vector database synchronized successfully from {start_date} to {end_date}.",
                "details": {
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "days_processed": (end_date - start_date).days + 1,
                    "levels_touched": {
                        "daily": touched_daily,
                        "weekly": touched_weekly,
                        "monthly": touched_monthly,
                        "yearly": touched_yearly
                    }
                }
            }
        finally:
            self.is_syncing = False
