import asyncio

from services.ollama_client import OllamaClient


async def main():

    client = OllamaClient()

    result = await client.generate(
        system_prompt="Return valid JSON only.",
        user_prompt='Return {"status": "LOCAL MODEL WORKING"}',
    )

    print("\nFINAL RESULT:")
    print(result)


asyncio.run(main())