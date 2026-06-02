import asyncio
import sys
from typing import Any, List, Optional, Dict
sys.path.insert(0, r"C:\Users\N Balu\Documents\saloon\backend")

from agents.bi_agent import BIAgent
from autogen_core.models import LLMMessage, CreateResult, RequestUsage
from autogen_agentchat.messages import TextMessage

class MockClient:
    @property
    def model_info(self):
        return {
            "vision": False,
            "function_calling": True,
            "json_output": True,
            "family": "llama-3.3-70b",
            "structured_output": False,
        }

    async def create(
        self,
        messages: List[LLMMessage],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> CreateResult:
        with open("C:/Users/N Balu/Documents/saloon/backend/scratch/bi_prompt_output.txt", "w", encoding="utf-8") as f:
            f.write("=== MESSAGES SENT TO LLM ===\n")
            for i, msg in enumerate(messages):
                f.write(f"[{i}] {type(msg).__name__}\n")
                f.write(f"Content: {msg.content}\n")
                f.write("-" * 40 + "\n")
            
            f.write("\n=== TOOLS SENT TO LLM ===\n")
            import pprint
            f.write(pprint.pformat(tools) + "\n")
        
        # Stop execution by returning dummy text
        return CreateResult(
            finish_reason="stop",
            content="Dummy response",
            usage=RequestUsage(prompt_tokens=0, completion_tokens=0),
            cached=False
        )

async def main():
    agent = BIAgent("Atlas_BI")
    # Replace the model client with our mock to inspect arguments
    agent.assistant._model_client = MockClient()
    
    # Run the assistant with a simple query
    await agent.assistant.on_messages(
        messages=[TextMessage(content="How was our revenue today?", source="user")],
        cancellation_token=None
    )

if __name__ == "__main__":
    asyncio.run(main())
