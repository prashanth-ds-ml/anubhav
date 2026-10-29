"""Bounded tool-calling loops over the business tools.

- run_chat: Chat Completions with tools passed directly (arm A: all 40; B0: the 8 core tools).
- run_responses: Responses API with every tool deferred in namespaces and Muse hosted tool search (arm B).

Both return the same AgentRun, so the grader never depends on the arm.
"""

import json
import os
import time
from dataclasses import dataclass, field

from . import tools
from .llm import BASE_URL, DEFAULT_MODEL, MuseClient, cost_usd

MAX_TURNS = 12

SYSTEM = (
    "You are the order-desk assistant of a wholesale FMCG distributor in Andhra Pradesh. Requests come from "
    "the operator in English, Telugu script, Roman Telugu or a mix. Use the tools to look up customers, "
    "products, units, stock, history and policies; never invent them. Follow the business policies "
    "(get_policies). When the request is clear, create exactly one draft quote with create_draft_quote, then "
    "reply with a short summary. If the customer or product is ambiguous, or a quote is not allowed, do not "
    "create a quote: explain why or ask the operator a clarifying question. Never confirm orders."
)  # identical across arms, and to the first B0 run, so only the tool setup differs


@dataclass
class AgentRun:
    final: str = ""
    trace: list[dict] = field(default_factory=list)       # tool calls with args and results
    searches: list[list[str]] = field(default_factory=list)  # tool-search paths (arm B)
    turns: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    hit_turn_limit: bool = False


def _run_tool(conn, run: AgentRun, name: str, raw_args: str) -> str:
    name = name.rsplit(".", 1)[-1]  # namespaced calls arrive as "customers.find_customer"
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        args, result = {}, {"error": "arguments are not valid JSON"}
    else:
        result = tools.call(conn, name, args)
    run.trace.append({"tool": name, "args": args, "result": result})
    return json.dumps(result, ensure_ascii=False, default=str)


def run_chat(conn, request: str, client: MuseClient, tool_names: list[str] | None = None, system: str = SYSTEM) -> AgentRun:
    run = AgentRun()
    schema = tools.chat_tools(tool_names)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": request}]
    for _ in range(MAX_TURNS):
        r = client.chat(messages, schema, temperature=0)
        run.turns += 1
        run.tokens_in, run.tokens_out = run.tokens_in + r.tokens_in, run.tokens_out + r.tokens_out
        run.cost_usd += r.cost_usd
        run.latency_s += r.latency_s
        messages.append(r.assistant_message())
        if not r.tool_calls:
            run.final = r.content or ""
            return run
        for tc in r.tool_calls:
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": _run_tool(conn, run, tc.name, tc.arguments)})
    run.hit_turn_limit = True
    return run


def responses_client():
    from openai import OpenAI

    return OpenAI(base_url=BASE_URL, api_key=os.environ["meta_api"])


def run_responses(conn, request: str, client, model: str = DEFAULT_MODEL, system: str = SYSTEM) -> AgentRun:
    run = AgentRun()
    schema = tools.responses_tools()
    inputs, prev = request, None
    for _ in range(MAX_TURNS):
        t0 = time.perf_counter()
        r = client.responses.create(model=model, instructions=system, input=inputs, tools=schema,
                                    previous_response_id=prev, temperature=0)
        run.latency_s += time.perf_counter() - t0
        run.turns += 1
        run.tokens_in += r.usage.input_tokens
        run.tokens_out += r.usage.output_tokens
        run.cost_usd += cost_usd(model, r.usage.input_tokens, r.usage.output_tokens)
        outputs = []
        for item in r.output:
            if item.type == "tool_search_call":
                run.searches.append(list((item.arguments or {}).get("paths", [])))
            elif item.type == "function_call":
                outputs.append({"type": "function_call_output", "call_id": item.call_id,
                                "output": _run_tool(conn, run, item.name, item.arguments)})
        if not outputs:
            run.final = r.output_text or ""
            return run
        inputs, prev = outputs, r.id
    run.hit_turn_limit = True
    return run
