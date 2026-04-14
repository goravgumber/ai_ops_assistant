"""Shared OpenRouter LLM client and request cost tracking utilities."""

from __future__ import annotations

import os
from typing import Any

import tiktoken
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class LLMClient:
    """Wrapper around OpenRouter's OpenAI-compatible chat completions API."""

    def __init__(self) -> None:
        """Initialize OpenRouter client configuration from environment variables."""
        api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        if not api_key:
            raise SystemExit(
                "OPENROUTER_API_KEY not found in .env file.\n"
                "Get your key from https://openrouter.ai/keys"
            )

        self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku").strip() or "anthropic/claude-3-haiku"
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

        print(f"✅ LLM Client ready — Model: {self.model}")
        print("✅ Provider: OpenRouter")

    def chat(self, system_prompt: str, user_message: str, expect_json: bool = False) -> str:
        """Send a chat request and return the model text response."""
        try:
            final_system_prompt = system_prompt
            if expect_json:
                final_system_prompt += (
                    "\nYou must respond ONLY with valid JSON."
                    "\nNo explanation. No markdown code blocks."
                    "\nNo backticks. Raw JSON only."
                )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": final_system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=2000,
                temperature=0.7,
                extra_headers={
                    "HTTP-Referer": "http://localhost:3000",
                    "X-Title": "AI Operations Assistant",
                },
            )

            content = response.choices[0].message.content if response.choices else ""
            return (content or "").strip()
        except Exception as e:
            raise RuntimeError(f"Failed to complete LLM request: {str(e)}") from e

    def count_tokens(self, text: str) -> int:
        """Estimate token count for text using cl100k_base encoding."""
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return int(len(encoding.encode(text or "")))
        except Exception:
            return int(len(text or "") // 4)


class CostTracker:
    """Tracks estimated token usage and request costs for LLM interactions."""

    INPUT_COST_PER_1K = 0.001
    OUTPUT_COST_PER_1K = 0.005

    def __init__(self) -> None:
        """Initialize an empty in-memory request cost log."""
        self.log_entries: list[dict[str, Any]] = []

    def log(self, agent_name: str, input_text: str, output_text: str) -> None:
        """Log a request's estimated input/output token counts and USD cost."""
        input_tokens = llm_client.count_tokens(input_text)
        output_tokens = llm_client.count_tokens(output_text)

        input_cost = (input_tokens / 1000) * self.INPUT_COST_PER_1K
        output_cost = (output_tokens / 1000) * self.OUTPUT_COST_PER_1K
        total_cost = input_cost + output_cost

        self.log_entries.append(
            {
                "agent": agent_name,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(total_cost, 6),
            }
        )

    def get_summary(self) -> dict[str, Any]:
        """Return aggregate usage statistics and detailed request logs."""
        total_input_tokens = sum(entry["input_tokens"] for entry in self.log_entries)
        total_output_tokens = sum(entry["output_tokens"] for entry in self.log_entries)
        total_cost = sum(entry["cost_usd"] for entry in self.log_entries)

        return {
            "total_requests": len(self.log_entries),
            "total_input_tokens": total_input_tokens,
            "total_output_tokens": total_output_tokens,
            "total_cost_usd": round(total_cost, 6),
            "log": self.log_entries,
        }

    def reset(self) -> None:
        """Clear all tracked cost log entries."""
        self.log_entries.clear()


llm_client = LLMClient()
cost_tracker = CostTracker()


if __name__ == "__main__":
    print("Testing OpenRouter connection...")
    response = llm_client.chat(
        "You are a helpful assistant.",
        "Say hello in one sentence.",
        expect_json=False,
    )
    print(f"✅ Response: {response}")
    cost_tracker.log("test", "hello", response)
    print(f"✅ Cost tracking: {cost_tracker.get_summary()}")
