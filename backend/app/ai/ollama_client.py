import os
from ollama import Client

class OllamaClient:
    """Client used by Zebio to communicate with the local Ollama server."""

    def __init__(
        self,
        host: str | None = None,
        model: str | None = None,
    ):
        self.host = host or "http://localhost:11434"

        self.model = model or os.getenv(
            "ZEBIO_LLM_MODEL",
            "qwen2.5-coder:14b",
        )

        self.client = Client(host=self.host)

    def chat(self, messages: list[dict]) -> str:
        """Send a conversation to the configured local model."""

        response = self.client.chat(
            model=self.model,
            messages=messages,
        )

        return response.message.content or ""

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
    ):
        """Send a conversation to Ollama with available tool definitions."""

        return self.client.chat(
            model=self.model,
            messages=messages,
            tools=tools,
        )    