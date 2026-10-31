"""Meta Muse adapters: chat with tools (Muse Spark via the Meta Model API, Muse Spark Open via Baseten),
speech-to-text (Muse Voice Transcribe), and a scripted mock for tests. Every chat call returns usage and cost,
so traces and the cost ledger never depend on which backend ran. Ported from the prototype's order_agent.llm."""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

BASE_URL = "https://api.meta.ai/v1"
DEFAULT_MODEL = "muse-spark-1.3"
BASETEN_URL = "https://inference.baseten.co/v1"
OPEN_MODEL = "meta-models/muse-spark-open-1026"   # the hackathon key only works with this exact id
ASR_URL = "https://api.meta.ai/v1/asr/transcribe"
ASR_MODEL = "muse-voice-transcribe-1.0"
ASR_USD_PER_HOUR = 0.18
TIMEOUT_S = 90          # one chat call; the SDK's default (600 s) would hang a hosted page
MAX_RETRIES = 3         # the SDK retries rate limits (429) and overloads (5xx) on its own
KEYS = {"spark": "meta_api", "open": "baseten_api_key"}

PRICES = {  # USD per 1M tokens (input, output), checked 2026-10-27
    "muse-spark-1.3": (1.25, 4.25),
    "muse-spark-1.2": (1.25, 4.25),
    OPEN_MODEL: (1.25, 4.25),
}


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str          # raw JSON string from the model; validated by the broker before use


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

    def assistant_message(self) -> dict:
        msg = {"role": "assistant", "content": self.content or ""}
        if self.tool_calls:
            msg["tool_calls"] = [{"id": tc.id, "type": "function", "function": {"name": tc.name, "arguments": tc.arguments}}
                                 for tc in self.tool_calls]
        return msg


class MissingKeyError(RuntimeError):
    """No key for this backend: the app falls back to replay instead of crashing."""


def key_for(name: str) -> str:
    """'spark' (Meta Model API) or 'open' (Baseten). Raises MissingKeyError rather than KeyError."""
    key = os.environ.get(KEYS[name], "").strip()
    if not key:
        raise MissingKeyError(f"{KEYS[name]} is not set: live Muse calls are off (add it to .env or the host's secrets)")
    return key


def cost_usd(model, tokens_in, tokens_out):
    p_in, p_out = PRICES.get(model, PRICES[DEFAULT_MODEL])
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


class MuseClient:
    """OpenAI-compatible Chat Completions client for Muse Spark (Meta API) or Muse Spark Open (Baseten)."""

    def __init__(self, model=DEFAULT_MODEL, api_key=None, base_url=BASE_URL, http_client=None, **defaults):
        from openai import OpenAI

        self.model, self.defaults = model, defaults
        self._client = OpenAI(base_url=base_url, api_key=api_key or key_for("spark"), timeout=TIMEOUT_S,
                              max_retries=MAX_RETRIES, http_client=http_client)

    def chat(self, messages, tools=None, **kw) -> ModelResponse:
        t0 = time.perf_counter()
        resp = self._client.chat.completions.create(model=self.model, messages=messages, tools=tools or None,
                                                    **{**self.defaults, **kw})
        choice, usage = resp.choices[0], resp.usage
        return ModelResponse(
            content=choice.message.content,
            tool_calls=[ToolCall(tc.id, tc.function.name, tc.function.arguments) for tc in (choice.message.tool_calls or [])],
            finish_reason=choice.finish_reason, model=resp.model, tokens_in=usage.prompt_tokens,
            tokens_out=usage.completion_tokens, latency_s=round(time.perf_counter() - t0, 3),
            cost_usd=cost_usd(self.model, usage.prompt_tokens, usage.completion_tokens))


def open_weights_client(**defaults) -> MuseClient:
    return MuseClient(OPEN_MODEL, key_for("open"), BASETEN_URL, **defaults)


def client(name: str = "spark", **defaults):
    """'open' = Muse Spark Open on Baseten, 'spark' = Muse Spark 1.3 on the Meta API."""
    return open_weights_client(**defaults) if name == "open" else MuseClient(**defaults)


class MockClient:
    """Scripted stand-in: each step is a ModelResponse or a callable (messages, tools) -> ModelResponse."""

    def __init__(self, script: list, model="mock"):
        self.model, self.script, self.calls = model, list(script), []

    def chat(self, messages, tools=None, **kw):
        self.calls.append({"messages": list(messages), "tools": tools})
        if not self.script:
            raise RuntimeError("MockClient script exhausted")
        step = self.script.pop(0)
        return step(messages, tools) if callable(step) else step


def mock_tool_call(name, args, call_id=None, content=None):
    return ModelResponse(content, [ToolCall(call_id or f"call_{name}", name, json.dumps(args, ensure_ascii=False))],
                         "tool_calls", "mock")


def mock_final(content):
    return ModelResponse(content, [], "stop", "mock")


def transcribe(wav: Path, language_bias=("Telugu", "English"), keywords=()) -> dict:
    """Muse Voice Transcribe on a mono 16-bit PCM WAV (16 or 24 kHz, <= 10 min)."""
    import httpx

    settings = {"mode": "PUSH_TO_TALK", "model": ASR_MODEL, "audioEncoding": "WAV"}
    if language_bias:
        settings["languageBias"] = list(language_bias)
    if keywords:
        settings["keywords"] = list(keywords)
    t0 = time.perf_counter()
    with Path(wav).open("rb") as f:
        r = httpx.post(ASR_URL, headers={"Authorization": f"Bearer {key_for('spark')}", "Accept": "application/json"},
                       files={"request": (None, json.dumps(settings), "application/json"),
                              "audio": (Path(wav).name, f, "audio/wav")}, timeout=120)
    r.raise_for_status()
    body = r.json()
    ms = body.get("audioDurationMs") or 0
    return {"transcript": body.get("transcript", ""), "audio_ms": ms, "latency_s": round(time.perf_counter() - t0, 2),
            "cost_usd": round(ms / 3_600_000 * ASR_USD_PER_HOUR, 6)}
