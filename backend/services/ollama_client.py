import json
import httpx


class OllamaClient:

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3:4b",
    ):
        self.base_url = base_url
        self.model = model

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> dict:

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],

            # Important for Qwen3:
            # disable extended thinking for fast structured extraction
            "think": False,

            # We need the complete JSON response
            "stream": False,

            # Ask Ollama for JSON output
            "format": "json",

            "options": {
                "temperature": 0.1,
                "num_ctx": 4096,
                "num_predict": 1000,
            },

            # Don't keep the model in RAM after the request
            "keep_alive": 0,
        }

        timeout = httpx.Timeout(
            connect=30.0,
            read=600.0,
            write=30.0,
            pool=30.0,
        )

        print("========================================")
        print("Sending request to Ollama...")
        print(f"URL: {self.base_url}/api/chat")
        print(f"Model: {self.model}")
        print("Thinking: disabled")
        print("========================================")

        async with httpx.AsyncClient(timeout=timeout) as client:

            response = await client.post(
                f"{self.base_url}/api/chat",
                json=payload,
            )

        print("Ollama HTTP response received.")

        response.raise_for_status()

        result = response.json()

        print("Ollama response parsed.")

        content = result["message"]["content"]

        print("========================================")
        print("OLLAMA CONTENT:")
        print(content)
        print("========================================")

        return json.loads(content)