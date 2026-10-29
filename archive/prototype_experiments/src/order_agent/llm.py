"""Model adapter: one interface for the real Muse API and a scripted mock.

Every call returns a ModelResponse with usage and cost, so traces and the cost ledger
never depend on which backend ran. Use MockClient for unit/UI tests (no credits spent).
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[4] / ".env")  # repo-root .env (this package lives in archive/prototype_experiments/)

BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"

# Open weights: Muse Spark Open on Baseten. The hackathon key only works with this exact model ID.
BASETEN_URL = "https://inference.baseten.co/v1"
OPEN_MODEL = "meta-models/muse-spark-open-1026"

# USD per 1M tokens (input, output), verified 2026-10-27 on the Meta pricing page.
PRICES = {
    "muse-spark-1.3": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    "muse-spark-1.3-contributor": (0.10, 0.20),
    "muse-spark-1.2-contributor": (0.10, 0.20),
    OPEN_MODEL: (1.25, 4.25),  # Baseten, per third-party trackers 2026-10-27; confirm on Baseten billing
}


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON string as returned by the model; validate before use

    def parsed_args(self) -> dict:
        return json.loads(self.arguments or "{}")


@dataclass
class ModelResponse:
    content: str | None
    tool_calls: list[ToolCall]
    finish_reason: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0
    raw: dict = field(default_factory=dict)

    def assistant_message(self) -> dict:
        """The assistant turn to append to history (required before tool results)."""
        msg = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [
                {"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                for tc in self.tool_calls
            ]
        return msg


def cost_usd(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = PRICES.get(model, PRICES[DEFAULT_MODEL])
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


class MuseClient:
    """Meta Model API via the OpenAI-compatible Chat Completions endpoint."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None, base_url: str = BASE_URL, **defaults):
        from openai import OpenAI

        self.model = model
        self.defaults = defaults
        self._client = OpenAI(base_url=base_url, api_key=api_key or os.environ["meta_api"])

    def chat(self, messages: list[dict], tools: list[dict] | None = None, **kw) -> ModelResponse:
        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, tools=tools or None, **{**self.defaults, **kw}
        )
        latency = time.perf_counter() - t0
        choice = resp.choices[0]
        usage = resp.usage
        return ModelResponse(
            content=choice.message.content,
            tool_calls=[
                ToolCall(tc.id, tc.function.name, tc.function.arguments) for tc in (choice.message.tool_calls or [])
            ],
            finish_reason=choice.finish_reason,
            model=resp.model,
            tokens_in=usage.prompt_tokens,
            tokens_out=usage.completion_tokens,
            latency_s=round(latency, 3),
            cost_usd=cost_usd(self.model, usage.prompt_tokens, usage.completion_tokens),
            raw=resp.model_dump(),
        )


def open_weights_client(**defaults) -> MuseClient:
    """Muse Spark Open on Baseten, same OpenAI-compatible interface as MuseClient."""
    return MuseClient(OPEN_MODEL, os.environ["baseten_api_key"].strip(), BASETEN_URL, **defaults)


class MockClient:
    """Scripted stand-in for MuseClient. No network, no cost.

    `script` is a list of steps consumed in order; each step is either a ModelResponse,
    or a callable (messages, tools) -> ModelResponse for responses that depend on input.
    """

    def __init__(self, script: list[ModelResponse | Callable[[list, list | None], ModelResponse]], model: str = "mock"):
        self.model = model
        self.script = list(script)
        self.calls: list[dict] = []

    def chat(self, messages: list[dict], tools: list[dict] | None = None, **kw) -> ModelResponse:
        self.calls.append({"messages": list(messages), "tools": tools, "kw": kw})
        if not self.script:
            raise RuntimeError("MockClient script exhausted")
        step = self.script.pop(0)
        return step(messages, tools) if callable(step) else step


def mock_tool_call(name: str, args: dict, call_id: str | None = None, content: str | None = None) -> ModelResponse:
    return ModelResponse(
        content=content,
        tool_calls=[ToolCall(call_id or f"call_{name}", name, json.dumps(args, ensure_ascii=False))],
        finish_reason="tool_calls",
        model="mock",
    )


def mock_final(content: str) -> ModelResponse:
    return ModelResponse(content=content, tool_calls=[], finish_reason="stop", model="mock")
