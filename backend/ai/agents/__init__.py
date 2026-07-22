"""AI Agents module using Microsoft AutoGen — Phase 1 Architecture"""

from typing import Dict, Any, Optional


class Agent:
    """Base agent class"""
    
    def __init__(self, name: str, role: str):
        """Initialize agent"""
        self.name = name
        self.role = role
    
    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input and return output"""
        pass


class AgentOrchestrator:
    """Orchestrates multiple agents"""
    
    def __init__(self):
        """Initialize agent orchestrator"""
        self.agents: Dict[str, Agent] = {}
    
    def register_agent(self, agent: Agent) -> None:
        """Register an agent"""
        self.agents[agent.name] = agent
    
    async def execute(self, agent_name: str, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a specific agent"""
        if agent_name not in self.agents:
            raise ValueError(f"Agent '{agent_name}' not found")
        return await self.agents[agent_name].process(input_data)


from ai.agents.receptionist_agent import ReceptionistAgent
from ai.agents.lead_followup_agent import LeadFollowupAgent
from ai.agents.reputation_agent import ReputationAgent
from ai.agents.upsell_agent import UpsellAgent
from ai.agents.staff_assistant_agent import StaffAssistantAgent
from ai.agents.bi_agent import BIAgent


def __getattr__(name: str):
    if name in (
        "MultiAgentOrchestrator",
        "get_phase1_orchestrator",
        "get_entity_resolver",
        "get_conversation_state_service",
        "get_permission_guard",
    ):
        import ai.orchestrator as orchestrator_mod
        return getattr(orchestrator_mod, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # Base classes
    "Agent",
    "AgentOrchestrator",
    # Specialist agents (all preserved)
    "ReceptionistAgent",
    "LeadFollowupAgent",
    "ReputationAgent",
    "UpsellAgent",
    "StaffAssistantAgent",
    "BIAgent",
    # Orchestrators
    "MultiAgentOrchestrator",      # legacy (backward-compatible)
    "get_phase1_orchestrator",     # Phase 1 factory
    # Phase 1 service accessors
    "get_entity_resolver",
    "get_conversation_state_service",
    "get_permission_guard",
]


