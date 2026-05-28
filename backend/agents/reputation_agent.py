"""
Reputation & Review Management AI Agent for SalonAI Workforce Platform.
Built using Microsoft AutoGen (agentchat v0.4+ / v0.10+).

Monitors customer reviews across platforms, performs sentiment analysis,
generates brand-safe professional responses, detects critical reviews,
and provides escalation workflows for negative feedback.
"""

import os
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

# AutoGen modern imports
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

# Project imports
from agents import Agent
from core.config import get_settings
from tools.reputation_tools import (
    fetch_reviews,
    get_review_analytics,
    detect_critical_reviews,
    generate_review_response,
    get_reputation_scorecard,
)

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Decoupled Wrapper Tools (exposes clean function schemas to LLM)
# ---------------------------------------------------------------------------
def view_customer_reviews(
    branch_id: Optional[str] = None,
    status: Optional[str] = None,
    min_rating: Optional[int] = None,
    max_rating: Optional[int] = None,
    limit: int = 50,
) -> str:
    """
    Fetch customer reviews from the database with optional filtering.
    Returns review details including sentiment, themes, and customer info.

    Args:
        branch_id: Optional UUID string to filter reviews by branch.
        status: Optional review moderation status ('PENDING', 'APPROVED', 'REJECTED').
        min_rating: Optional minimum star rating (1-5).
        max_rating: Optional maximum star rating (1-5).
        limit: Maximum number of reviews to return (default 50).
    """
    logger.info(
        f"[ReputationAgent] Tool call: view_customer_reviews("
        f"branch={branch_id}, status={status}, min={min_rating}, max={max_rating})"
    )
    result = fetch_reviews(
        branch_id=branch_id, status=status,
        min_rating=min_rating, max_rating=max_rating, limit=limit,
    )
    return str(result)


def view_review_analytics(
    branch_id: Optional[str] = None,
    days: int = 30,
) -> str:
    """
    Generate aggregated review analytics including star distribution,
    sentiment breakdown, average rating trends, and top feedback themes.

    Args:
        branch_id: Optional UUID string to scope analytics to a branch.
        days: Look-back window in days (default 30).
    """
    logger.info(
        f"[ReputationAgent] Tool call: view_review_analytics(branch={branch_id}, days={days})"
    )
    result = get_review_analytics(branch_id=branch_id, days=days)
    return str(result)


def find_critical_reviews(
    rating_threshold: int = 2,
    branch_id: Optional[str] = None,
    days: int = 7,
) -> str:
    """
    Detect critical (negative) reviews that require immediate management attention.
    Returns reviews at or below the rating threshold within the look-back window,
    including escalation flags for 1-star reviews.

    Args:
        rating_threshold: Maximum star rating to flag as critical (default 2).
        branch_id: Optional UUID string to scope detection to a branch.
        days: Look-back window in days (default 7).
    """
    logger.info(
        f"[ReputationAgent] Tool call: find_critical_reviews("
        f"threshold={rating_threshold}, branch={branch_id}, days={days})"
    )
    result = detect_critical_reviews(
        rating_threshold=rating_threshold, branch_id=branch_id, days=days,
    )
    return str(result)


def draft_review_response(
    review_id: str,
    tone: str = "professional",
) -> str:
    """
    Generate a brand-safe, professional response to a specific customer review.
    Tone adapts based on the review's sentiment and selected tone profile.

    Args:
        review_id: UUID string of the review to respond to.
        tone: Response tone — 'professional', 'empathetic', 'warm', or 'formal'.
    """
    logger.info(
        f"[ReputationAgent] Tool call: draft_review_response(review={review_id}, tone={tone})"
    )
    result = generate_review_response(review_id=review_id, tone=tone)
    return str(result)


def view_reputation_scorecard(
    branch_id: Optional[str] = None,
) -> str:
    """
    Generate a comprehensive reputation scorecard with NPS-style metrics,
    review status distribution, and per-branch rating comparisons.

    Args:
        branch_id: Optional UUID string to scope scorecard to a single branch.
    """
    logger.info(
        f"[ReputationAgent] Tool call: view_reputation_scorecard(branch={branch_id})"
    )
    result = get_reputation_scorecard(branch_id=branch_id)
    return str(result)


# ---------------------------------------------------------------------------
# Conversational System Prompt
# ---------------------------------------------------------------------------
REPUTATION_SYSTEM_PROMPT = """\
You are Olivia, the Reputation & Review Management Agent at SalonAI Workforce Platform.

🎯 CORE MISSION:
Monitor, analyse, and manage customer reviews across all salon branches.
Protect the brand reputation through proactive sentiment tracking, professional response
generation, and immediate escalation of critical negative feedback.

📋 YOUR CAPABILITIES:
1. **Review Browsing & Search** — Fetch and filter customer reviews by branch, status, or rating.
   Use `view_customer_reviews`.
2. **Review Analytics & Sentiment** — Generate star distribution, sentiment breakdowns, trending themes.
   Use `view_review_analytics` (supports branch scoping and custom time windows).
3. **Critical Review Detection** — Flag negative reviews (≤2 stars) for immediate attention.
   Use `find_critical_reviews` (includes escalation flags for 1-star reviews).
4. **Brand-Safe Response Drafting** — Generate professional responses tailored by tone and sentiment.
   Use `draft_review_response` (supports 'professional', 'empathetic', 'warm', 'formal' tones).
5. **Reputation Scorecard** — View overall NPS estimate, branch comparisons, and review status distribution.
   Use `view_reputation_scorecard`.

📏 RESPONSE GUIDELINES:
- Always cite actual data from your tools. Never fabricate reviews or ratings.
- When presenting review summaries, use Markdown tables for star distributions.
- For critical reviews, clearly flag the severity (🔴 Critical / 🟡 High).
- When drafting responses, present them in quote blocks for easy copy-paste.
- Highlight actionable insights (e.g., "Wait times mentioned in 30% of negative reviews").
- Recommend specific follow-up actions for negative trends.

🛡️ BRAND SAFETY RULES:
- Never include customer personally identifiable information in public-facing responses.
- Response drafts must be empathetic and solution-oriented — never defensive or dismissive.
- Escalate all 1-star reviews automatically with a clear recommendation.
- Maintain a professional, calm tone regardless of review content.

🎨 COMMUNICATION STYLE:
- Be analytical yet empathetic. Balance data-driven insights with human understanding.
- Use clear headings, bullet points, and tables for readability.
- Present sentiment trends visually with percentage breakdowns.
- Summarize key takeaways and recommended actions at the end of every analysis.
"""


# ---------------------------------------------------------------------------
# Agent Class
# ---------------------------------------------------------------------------
class ReputationAgent(Agent):
    """
    Reputation & Review Management AI Agent powered by Microsoft AutoGen v0.4+ and Groq LLM.
    Provides comprehensive review monitoring, sentiment analysis, response generation,
    critical review detection, and brand reputation scoring.
    """

    def __init__(self, name: str = "Olivia", role: str = "Reputation & Review Manager"):
        super().__init__(name=name, role=role)
        logger.info(f"Initializing Reputation Agent '{name}'...")

        self._conversation_memory: Dict[str, List[Dict[str, str]]] = {}
        self._analytics: Dict[str, int] = {
            "queries_processed": 0,
            "review_fetches": 0,
            "analytics_queries": 0,
            "critical_detections": 0,
            "responses_drafted": 0,
            "scorecard_views": 0,
        }

        # 1. Configure model client - Groq (free, open-source alternative to OpenAI)
        groq_key = settings.groq_api_key or os.environ.get("GROQ_API_KEY")

        if groq_key and groq_key != "your-groq-key-here":
            logger.info("Configuring ReputationAgent with Groq endpoint...")
            self.model_client = OpenAIChatCompletionClient(
                model="llama-3.3-70b-specdec",
                api_key=groq_key,
                base_url="https://api.groq.com/openai/v1",
            )
        else:
            logger.warning("No Groq API key found – ReputationAgent using mock client for testing.")
            self.model_client = OpenAIChatCompletionClient(
                model="llama-3.3-70b-specdec",
                api_key="mock-groq-key-for-testing",
                base_url="https://api.groq.com/openai/v1",
            )

        # 2. Build AutoGen AssistantAgent with full tool suite
        self.assistant = AssistantAgent(
            name=name,
            model_client=self.model_client,
            system_message=REPUTATION_SYSTEM_PROMPT,
            tools=[
                view_customer_reviews,
                view_review_analytics,
                find_critical_reviews,
                draft_review_response,
                view_reputation_scorecard,
            ],
        )

        logger.info(f"Reputation Agent '{name}' initialized with 5 review management tools.")

    def _get_memory_context(self, session_id: str) -> str:
        """Build conversation context string from memory for a given session."""
        history = self._conversation_memory.get(session_id, [])
        if not history:
            return ""

        context_lines = ["Here is the conversation history so far for context:"]
        for entry in history[-10:]:
            role = entry.get("role", "user").capitalize()
            content = entry.get("content", "")
            context_lines.append(f"- {role}: {content}")
        context_lines.append("")
        return "\n".join(context_lines)

    def _store_memory(self, session_id: str, role: str, content: str) -> None:
        """Store a message in session memory."""
        if session_id not in self._conversation_memory:
            self._conversation_memory[session_id] = []
        self._conversation_memory[session_id].append({
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def clear_memory(self, session_id: str) -> None:
        """Clear conversation memory for a specific session."""
        if session_id in self._conversation_memory:
            del self._conversation_memory[session_id]
            logger.info(f"[ReputationAgent] Cleared memory for session: {session_id}")

    def _track_analytics(self, category: str) -> None:
        """Increment an analytics counter."""
        if category in self._analytics:
            self._analytics[category] += 1

    def get_analytics(self) -> Dict[str, Any]:
        """Return current analytics counters."""
        return {
            "agent_name": self.name,
            "role": self.role,
            "metrics": dict(self._analytics),
            "active_sessions": len(self._conversation_memory),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Standardized entrypoint to process reputation and review management queries.

        Args:
            input_data: Dictionary containing:
                - "query": The user's natural language review/reputation query (required).
                - "session_id": Optional session identifier for conversation memory.
                - "chat_history": Optional list of prior messages for context.

        Returns:
            Dictionary containing:
                - "success": True/False
                - "response": Conversational response text from the agent
                - "agent_name": Name of this agent
                - "analytics": Current analytics counters
        """
        query = input_data.get("query")
        if not query:
            return {"success": False, "error": "Input data must contain a 'query' key."}

        session_id = input_data.get("session_id", "default")
        chat_history = input_data.get("chat_history", [])

        logger.info(f"[ReputationAgent] Processing query (session={session_id}): '{query[:100]}'")
        self._track_analytics("queries_processed")

        # Track category keywords for analytics telemetry
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["review", "reviews", "feedback", "comment"]):
            self._track_analytics("review_fetches")
        if any(kw in query_lower for kw in ["analytics", "sentiment", "trend", "distribution", "theme"]):
            self._track_analytics("analytics_queries")
        if any(kw in query_lower for kw in ["critical", "negative", "bad", "complaint", "escalat"]):
            self._track_analytics("critical_detections")
        if any(kw in query_lower for kw in ["respond", "response", "draft", "reply"]):
            self._track_analytics("responses_drafted")
        if any(kw in query_lower for kw in ["score", "nps", "reputation", "scorecard"]):
            self._track_analytics("scorecard_views")

        try:
            full_query = ""

            # Prepend chat history if provided
            if chat_history:
                full_query += "Here is the conversation history so far for context:\n"
                for msg in chat_history:
                    role = msg.get("role", "user").capitalize()
                    content = msg.get("content", "")
                    full_query += f"- {role}: {content}\n"
                full_query += "\n"

            # Prepend session memory
            memory_context = self._get_memory_context(session_id)
            if memory_context and not chat_history:
                full_query += memory_context + "\n"

            full_query += f"Latest User Message: {query}"

            # Store user query in memory
            self._store_memory(session_id, "user", query)

            # Execute AutoGen AssistantAgent run task
            result = await self.assistant.run(task=full_query)

            # Extract response text
            response_text = result.messages[-1].content

            # Store assistant response in memory
            self._store_memory(session_id, "assistant", response_text)

            logger.info(f"[ReputationAgent] Query processed successfully (session={session_id})")

            return {
                "success": True,
                "agent_name": self.name,
                "response": response_text,
                "session_id": session_id,
                "analytics": self.get_analytics(),
            }

        except Exception as e:
            logger.error(f"[ReputationAgent] Error processing query: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Reputation Agent processing failed: {str(e)}",
            }
