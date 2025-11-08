import os
import asyncio
from typing import Any
import anthropic

from agent_framework import ChatAgent, ChatMessage, AgentRunResponse

MODEL_ID = "claude-haiku-4-5-20251001"

# Anthropic API client for Claude models, compatible with ChatAgent.

class AnthropicChatClient:

    def __init__(self, api_key: str | None = None, model: str | None = None, max_tokens: int = 512):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("ANTHROPIC_MODEL", MODEL_ID)
        self.max_tokens = max_tokens
        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None

    # Call the Anthropic API with the given prompt.
    def _call_anthropic_api(self, prompt_text: str):
        formatted = f"\n\nHuman: {prompt_text}\n\nAssistant:"
        # Use the messages API with the latest SDK
        if hasattr(self.client, "messages") and hasattr(self.client.messages, "create"):
            return self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                messages=[{"role": "user", "content": formatted}]
            )
        # Fallback for older SDK versions with completions API
        if hasattr(self.client, "completions") and hasattr(self.client.completions, "create"):
            return self.client.completions.create(model=self.model, prompt=formatted, max_tokens_to_sample=self.max_tokens)
        # If none of the expected methods exist, raise an error
        raise RuntimeError("Anthropic client has no known completion method")

    # Interface with Microsoft Agent Framework's ChatAgent
    async def get_response(self, messages: Any = None, chat_options: dict | None = None, **kwargs) -> AgentRunResponse:
        # If no API key, return a mock reply so the smoke-test still works.
        if not self.api_key:
            resp = AgentRunResponse(messages=[ChatMessage(role="assistant", text="Mock reply (ANTHROPIC_API_KEY not set).")], response_id="mock")
            setattr(resp, "conversation_id", f"mock-{os.urandom(6).hex()}")
            return resp

        # Build a simple prompt from messages. The package may pass strings or lists.
        if messages is None:
            prompt_text = ""
        elif isinstance(messages, str):
            prompt_text = messages
        elif isinstance(messages, list):
            # join text elements; if elements are ChatMessage-like, try to read .text
            parts = []
            for m in messages:
                if hasattr(m, "text"):
                    parts.append(getattr(m, "text"))
                else:
                    parts.append(str(m))
            prompt_text = "\n".join(parts)
        else:
            prompt_text = str(messages)

        # Call the API in a thread to avoid blocking the event loop
        resp = await asyncio.to_thread(self._call_anthropic_api, prompt_text)

        # Normalize response (SDKs may return dicts or objects)
        if isinstance(resp, dict):
            text = resp.get("completion") or resp.get("completion_text") or resp.get("text") or ""
            # Handle messages API response format
            if "content" in resp and resp["content"]:
                content = resp["content"][0]
                if isinstance(content, dict):
                    text = content.get("text", "")
                else:
                    text = getattr(content, "text", "")
        else:
            # Handle object responses
            if hasattr(resp, "content"):
                content = resp.content[0] if resp.content else None
                text = getattr(content, "text", "") if content else ""
            else:
                text = getattr(resp, "completion", getattr(resp, "completion_text", getattr(resp, "text", "")))

        response = AgentRunResponse(messages=[ChatMessage(role="assistant", text=text)])
        # Some versions expect a conversation_id attribute on the response
        setattr(response, "conversation_id", f"anthropic-{os.urandom(6).hex()}")
        return response


async def main():
    client = AnthropicChatClient()
    print("Testing AnthropicChatClient with API key:", client.api_key)
    print("Model:", client.model)
    # ChatAgent is an async context manager; create it with our client and run.
    async with ChatAgent(chat_client=client, instructions="You are good at telling jokes.") as agent:
        result = await agent.run("Tell me a joke about a pirate.")
        print(result.text)

if __name__ == "__main__":
    asyncio.run(main())