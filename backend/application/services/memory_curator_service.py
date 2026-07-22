import json
import logging
import re
import datetime
from typing import Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

# Project imports
from core.llm_config import get_llm_config
from core.openai_client_adapter import OpenAIChatCompletionClient
from autogen_core.models import SystemMessage, UserMessage

from infrastructure.db.database import SessionLocal
from infrastructure.db.models import CuratedMemory, MemoryScope, MemoryStatus, ConsentClass
from infrastructure.rag.curated_faiss_store import CuratedFAISSStore
from infrastructure.events.event_bus import (
    get_event_bus,
    SalonEvent,
    CustomerPreferenceEvent,
    LeadStatusChangedEvent,
    UpsellOutcomeEvent,
    ReviewIssueEvent,
    StaffFeedbackEvent,
    CampaignDecisionEvent,
    AppointmentCompletedEvent
)

logger = logging.getLogger(__name__)


class HardPolicyEngine:
    """
    Layer 1: Deterministic allow/block rules.
    Decides without invoking the LLM if possible.
    """

    # Block patterns
    BLOCKED_KEYWORDS = [
        r"\bpassword\b", r"\botp\b", r"\bpin\b", r"\bverification code\b",
        r"\bmedical\b", r"\bhealth condition\b", r"\bdisease\b", r"\bsocial security\b",
        r"\bcredit card\b", r"\bcvv\b", r"\bcard number\b"
    ]

    TEMPORARY_PATTERNS = [
        r"what time do you close\b",
        r"are you open\b",
        r"how much for\b",
        r"appointment (at|on)\b"
    ]

    @classmethod
    def evaluate(cls, event: SalonEvent) -> Tuple[Optional[bool], Optional[str]]:
        """
        Returns (decision, reason).
        decision = True: Auto-approve storage
        decision = False: Auto-block/discard
        decision = None: Ambiguous, proceed to LLM evaluator
        """
        event_type = event.event_type
        payload = event.payload or {}
        text = str(payload.get("text", payload.get("comment", payload.get("message", payload.get("notes", "")))))

        # Rule 1: Block sensitive information (passwords, OTPs, credit cards, medical history)
        for pattern in cls.BLOCKED_KEYWORDS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, f"Blocked by Hard Policy: sensitive information detected ({pattern})"

        # Rule 2: Block raw chat transcripts
        if event_type == "salon.event" and payload.get("sender") in ("user", "assistant"):
            return False, "Blocked by Hard Policy: raw chat messages cannot be saved directly"

        # Rule 3: Block temporary questions / trivial interactions
        for pattern in cls.TEMPORARY_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return False, "Blocked by Hard Policy: temporary query/interaction"

        # Rule 4: Block raw live SQL facts if they are purely transactional
        # (e.g. AppointmentBookedEvent with just dates, no preferences)
        if event_type == "appointment.booked":
            # Live appointment dates are already in SQL
            return False, "Blocked by Hard Policy: appointment bookings are tracked in SQL only"

        # Rule 5: Auto-approve obvious durable customer preferences
        if event_type == "customer.preference" or "preference" in event_type:
            # Stated customer preference
            return True, "Auto-Approved: Explicit customer preference"

        # Rule 6: Auto-approve explicit communication restrictions
        if "communication" in event_type or "whatsapp" in text.lower() or "do not call" in text.lower():
            if "restrict" in text.lower() or "prefer" in text.lower() or "do not" in text.lower() or "only" in text.lower():
                return True, "Auto-Approved: Communication preference/restriction"

        # Rule 7: Auto-approve confirmed lead follow-up timing
        if event_type == "lead.status_changed" and payload.get("new_status") == "CONTACTED":
            if "follow up" in text.lower() or "call after" in text.lower():
                return True, "Auto-Approved: Lead follow-up timing details"

        # Rule 8: Auto-approve offer outcome
        if event_type == "upsell.outcome" or event_type in ("recommendation.accepted", "recommendation.rejected"):
            return True, "Auto-Approved: Confirmed upsell outcome"

        # Rule 9: Auto-approve resolved service issue / negative reviews with actions
        if event_type == "review.issue" and payload.get("rating") and payload.get("rating") <= 2:
            return True, "Auto-Approved: Resolved/Unresolved service issue for reputation tracking"

        # Rule 10: Auto-approve campaigns
        if event_type == "campaign.decision":
            return True, "Auto-Approved: Campaign and narrative business decisions"

        # Ambiguous case: pass to LLM
        return None, None


class LLMMemoryEvaluator:
    """
    Layer 2: LLM structured evaluation.
    Only triggered for ambiguous events.
    """

    def __init__(self):
        llm_config = get_llm_config()
        config = llm_config.get_config()
        self.model_client = OpenAIChatCompletionClient(
            model=config["model"],
            api_key=config["api_key"],
            base_url=config["base_url"],
            model_info=config["model_info"],
        )

    async def evaluate_event(self, event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ask structured LLM if this is durable, useful, stated, and returns a JSON payload.
        """
        system_prompt = (
            "You are a structured memory evaluation agent for an AI-powered salon management system.\n"
            "Your job is to read an event and determine if it represents a durable, high-value fact "
            "that should be remembered long-term. You must respond with a strict JSON object ONLY.\n\n"
            "Decision guidelines:\n"
            "1. Store only facts that remain true beyond the current conversation (e.g. preferences, stylist choices, restrictions, recurring complaints).\n"
            "2. DO NOT store live/date-specific facts (e.g. appointment date, invoice number, rating number) since they are in SQL.\n"
            "3. Reject guesses, opinions, raw logs, temporary questions, or generic chat.\n"
            "4. Assign importance (0.0 to 1.0) and confidence (0.0 to 1.0).\n"
            "5. Scope must be one of: 'customer', 'staff', 'lead', 'business', 'reputation', 'campaign'.\n"
            "6. Identify if this supersedes an older memory (provide reason if so).\n\n"
            "JSON Response schema:\n"
            "{\n"
            "  \"store\": true/false,\n"
            "  \"fact\": \"The synthesized memory string to store\",\n"
            "  \"scope\": \"customer/staff/lead/business/reputation/campaign\",\n"
            "  \"importance\": 0.8,\n"
            "  \"confidence\": 0.95,\n"
            "  \"expires_at\": \"YYYY-MM-DDTHH:MM:SSZ\" or null,\n"
            "  \"supersedes_reason\": \"older stylist preference\" or null,\n"
            "  \"reason\": \"Brief justification\"\n"
            "}"
        )

        user_content = (
            f"Event Type: {event_type}\n"
            f"Payload: {json.dumps(payload, default=str)}"
        )

        try:
            sys_msg = SystemMessage(content=system_prompt)
            user_msg = UserMessage(content=user_content, source="user")
            result = await self.model_client.create(
                messages=[sys_msg, user_msg],
                max_tokens=600,
                extra_create_params={"response_format": {"type": "json_object"}}
            )
            data = json.loads(result.content.strip())
            return data
        except Exception as e:
            logger.error(f"[LLMMemoryEvaluator] Evaluation failed: {e}", exc_info=True)
            return {
                "store": False,
                "fact": "",
                "scope": "customer",
                "importance": 0.0,
                "confidence": 0.0,
                "expires_at": None,
                "supersedes_reason": None,
                "reason": f"Failed evaluation: {str(e)}"
            }


class MemoryCuratorService:
    """
    Layer 3: Authority service.
    Coordinates policy checks, LLM evaluation, database updates, and local FAISS.
    """

    def __init__(self):
        self.evaluator = LLMMemoryEvaluator()
        self.vector_store = CuratedFAISSStore()

    async def process_event(self, db: Session, event: SalonEvent) -> Optional[CuratedMemory]:
        """
        Processes a domain event and saves it to curated_memories SQL + FAISS if it represents
        a durable and valid fact.
        """
        logger.info(f"[MemoryCuratorService] Processing event {event.event_id} ({event.event_type})")
        payload = dict(event.payload) if event.payload else {}
        
        # Inject standard parameters and custom fields from attributes if missing in payload
        for f_name in getattr(event, "__dataclass_fields__", {}):
            if f_name not in ("event_id", "event_type", "tenant_id", "timestamp", "payload"):
                val = getattr(event, f_name, None)
                if val is not None and f_name not in payload:
                    payload[f_name] = str(val) if not isinstance(val, bool) else val


        # Layer 1: Hard Policy
        decision, reason = HardPolicyEngine.evaluate(event)
        
        fact_text = ""
        scope_val = "customer"
        importance_val = 0.5
        confidence_val = 1.0
        expires_at_val = None
        
        if decision is False:
            logger.info(f"[MemoryCuratorService] Event {event.event_id} discarded: {reason}")
            return None
        
        elif decision is True:
            logger.info(f"[MemoryCuratorService] Event {event.event_id} auto-approved: {reason}")
            # Map standard event parameters to a readable fact
            if event.event_type == "customer.preference":
                pref_key = payload.get("preference_key", "")
                pref_val = payload.get("preference_value", "")
                fact_text = f"Customer preference: {pref_key} is set to {pref_val}."
                scope_val = "customer"
                importance_val = 0.8
            elif event.event_type == "upsell.outcome":
                accepted = payload.get("accepted", False)
                outcome = "accepted" if accepted else "rejected"
                svc = payload.get("service_id", "service")
                reason_str = f" due to: {payload.get('rejection_reason')}" if payload.get("rejection_reason") else ""
                fact_text = f"Upsell offer for service {svc} was {outcome}{reason_str}."
                scope_val = "customer"
                importance_val = 0.7
            elif event.event_type == "lead.status_changed":
                new_status = payload.get("new_status", "")
                notes = payload.get("notes", "")
                fact_text = f"Lead status updated to {new_status}. Customer notes: {notes}."
                scope_val = "lead"
                importance_val = 0.6
                # Set dynamic expiry (e.g. 30 days for leads follow-up)
                expires_at_val = datetime.datetime.now(timezone_utc := datetime.timezone.utc) + datetime.timedelta(days=30)
            elif event.event_type == "review.issue":
                comment = payload.get("comment", "")
                fact_text = f"Customer submitted critical feedback: '{comment}'."
                scope_val = "reputation"
                importance_val = 0.9
            elif event.event_type == "campaign.decision":
                camp = payload.get("campaign_name", "")
                dec = payload.get("decision", "")
                out = payload.get("outcome", "")
                fact_text = f"Campaign '{camp}' outcome: decision '{dec}' resulted in: {out}."
                scope_val = "campaign"
                importance_val = 0.85
            else:
                text_content = str(payload.get("text", payload.get("notes", payload.get("comment", "Valuable event recorded"))))
                fact_text = f"Event alert: {text_content}"
                scope_val = "business"
        
        else:
            # Layer 2: LLM Evaluator
            logger.info(f"[MemoryCuratorService] Event {event.event_id} is ambiguous. Running LLM Evaluator...")
            llm_result = await self.evaluator.evaluate_event(event.event_type, payload)
            
            if not llm_result.get("store", False):
                logger.info(f"[MemoryCuratorService] LLM Evaluator rejected event: {llm_result.get('reason')}")
                return None
            
            fact_text = llm_result.get("fact", "")
            scope_val = llm_result.get("scope", "customer")
            importance_val = llm_result.get("importance", 0.5)
            confidence_val = llm_result.get("confidence", 0.9)
            
            expires_at_str = llm_result.get("expires_at")
            if expires_at_str:
                try:
                    expires_at_val = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                except ValueError:
                    expires_at_val = None

        if not fact_text:
            logger.warning("[MemoryCuratorService] Approved memory, but fact text is empty. Discarding.")
            return None

        # Resolve owner identifier
        owner_id = payload.get("customer_id") or payload.get("staff_id") or payload.get("lead_id") or payload.get("owner_id")

        # Layer 3: Final validation & Supersession
        tenant_id = event.tenant_id or "default"
        
        # Check for supersession: if there is an existing memory that conflicts with this new one,
        # mark it as superseded
        if owner_id and scope_val in ("customer", "staff", "lead"):
            existing_conflicts = db.query(CuratedMemory).filter(
                CuratedMemory.tenant_id == tenant_id,
                CuratedMemory.scope == MemoryScope(scope_val),
                CuratedMemory.owner_id == str(owner_id),
                CuratedMemory.status == MemoryStatus.ACTIVE
            ).all()

            for old_mem in existing_conflicts:
                # Basic conflict logic: if the preference key matches or if the LLM suggests supersession
                # Let's say if the fact contains the same prefix key or same topic, we supersede it
                # For safety, let's look for matching keywords
                old_words = set(old_mem.content.lower().split())
                new_words = set(fact_text.lower().split())
                common = old_words.intersection(new_words)
                
                # If they have high overlap in context (e.g. both stylist name or communication channel), supersede
                if ("stylist" in old_mem.content.lower() and "stylist" in fact_text.lower()) or \
                   ("whatsapp" in old_mem.content.lower() and "whatsapp" in fact_text.lower()) or \
                   ("call" in old_mem.content.lower() and "call" in fact_text.lower()) or \
                   ("preference:" in old_mem.content.lower() and "preference:" in fact_text.lower()):
                    old_mem.status = MemoryStatus.SUPERSEDED
                    # Also delete old vector from FAISS
                    self.vector_store.delete(old_mem.id, tenant_id, scope_val)
                    logger.info(f"[MemoryCuratorService] Superseded old memory ID {old_mem.id}")

        # Save to database
        new_memory = CuratedMemory(
            tenant_id=tenant_id,
            scope=MemoryScope(scope_val),
            owner_id=str(owner_id) if owner_id else None,
            content=fact_text,
            source_event_id=event.event_id,
            source_type=event.event_type,
            status=MemoryStatus.ACTIVE,
            confidence=confidence_val,
            importance=importance_val,
            expires_at=expires_at_val
        )
        db.add(new_memory)
        db.commit()
        db.refresh(new_memory)

        # Update FAISS
        self.vector_store.upsert(
            memory_id=str(new_memory.id),
            text=fact_text,
            metadata={
                "tenant_id": tenant_id,
                "scope": scope_val,
                "owner_id": str(owner_id) if owner_id else "",
                "importance": importance_val,
                "confidence": confidence_val,
                "expires_at": expires_at_val
            }
        )

        logger.info(f"[MemoryCuratorService] Successfully curated and saved memory ID {new_memory.id} to SQL & FAISS")
        return new_memory

    def forget_memory(self, db: Session, memory_id: Any, tenant_id: str = "default") -> bool:
        """
        Deletes a memory record completely from PostgreSQL metadata and local FAISS vector index.
        """
        memory = db.query(CuratedMemory).filter(
            CuratedMemory.id == memory_id,
            CuratedMemory.tenant_id == tenant_id
        ).first()

        if not memory:
            logger.warning(f"[MemoryCuratorService] Attempted to delete non-existent memory {memory_id}")
            return False

        # Mark deleted in SQL (soft delete or hard delete; here we delete it to maintain clean privacy guarantees)
        scope = memory.scope.value
        db.delete(memory)
        db.commit()

        # Remove from local FAISS
        self.vector_store.delete(str(memory_id), tenant_id, scope)
        logger.info(f"[MemoryCuratorService] Permanently deleted memory {memory_id} from SQL & FAISS")
        return True


# Event bus subscription registration
def register_memory_curator_subscribers() -> None:
    """Register the curator process event subscriber to event bus."""
    bus = get_event_bus()
    curator = MemoryCuratorService()

    def handle_event(event: SalonEvent):
        db = SessionLocal()
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(curator.process_event(db, event))
            loop.close()
        except Exception as e:
            logger.error(f"[MemoryCuratorSubscriber] Failed to process event {event.event_id}: {e}", exc_info=True)
        finally:
            db.close()

    # Subscribe to all event classes we care about
    event_types = [
        "customer.preference",
        "lead.status_changed",
        "upsell.outcome",
        "review.issue",
        "staff.feedback",
        "campaign.decision",
        "appointment.completed"
    ]
    for etype in event_types:
        bus.subscribe(etype, handle_event)
        logger.info(f"[MemoryCurator] Registered subscription handler for event_type: {etype}")
