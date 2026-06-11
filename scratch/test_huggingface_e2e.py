import sys
import os
import asyncio
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from core.llm_config import get_llm_config
from core.openai_client_adapter import OpenAIChatCompletionClient
from autogen_core.models import UserMessage


async def test():
    manager = get_llm_config()
    chain = manager.get_provider_chain()
    print('Provider chain:', [f"{c['provider']}:{c['model']}" for c in chain])

    # Use the FIRST provider in chain (should be Hugging Face)
    cfg = chain[0]
    print(f"Testing with: {cfg['provider']} -> {cfg['model']} @ {cfg['base_url']}")

    client = OpenAIChatCompletionClient(
        model=cfg['model'],
        api_key=cfg['api_key'],
        base_url=cfg['base_url'],
        timeout=30.0
    )

    result = await client.create(
        messages=[UserMessage(content='Say hello briefly.', source='user')],
        max_tokens=50
    )
    print('Response:', result.content)
    print('SUCCESS - Hugging Face is working!')


if __name__ == "__main__":
    asyncio.run(test())
