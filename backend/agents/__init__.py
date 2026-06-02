"""AI Agents module using Microsoft AutoGen"""

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


from agents.receptionist_agent import ReceptionistAgent
from agents.lead_followup_agent import LeadFollowupAgent
from agents.reputation_agent import ReputationAgent
from agents.upsell_agent import UpsellAgent
from agents.orchestrator import MultiAgentOrchestrator

__all__ = ["Agent", "AgentOrchestrator", "ReceptionistAgent", "LeadFollowupAgent", "ReputationAgent", "UpsellAgent", "MultiAgentOrchestrator"]
