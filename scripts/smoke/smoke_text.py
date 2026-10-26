"""Day-1 smoke tests T1-T5, T8 against the Meta Model API (Muse Spark).

Usage: uv run python scripts/smoke/smoke_text.py [--model muse-spark-1.3]
Writes raw results to artifacts/smoke/text_<timestamp>.json
"""

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PRICE_IN = {"muse-spark-1.3": 1.25, "muse-spark-1.3-contributor": 0.10}
PRICE_OUT = {"muse-spark-1.3": 4.25, "muse-spark-1.3-contributor": 0.20}

SYSTEM = (
    "You are an order-desk assistant for a wholesale distributor. Requests may be in English, "
    "Telugu script, Roman Telugu, or a mix. Use tools to look up facts; never invent customers, "
    "products, prices or stock. Never confirm orders when the user forbids it."
)


def fn(name, desc, props, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOLS = [
    fn("find_customer", "Find a customer by name or alias.", {"name": {"type": "string"}}, ["name"]),
    fn(
        "check_stock",
        "Check available stock for a product, in cartons.",
        {"product": {"type": "string"}},
        ["product"],
    ),
    fn(
        "create_draft_quote",
        "Create an editable DRAFT quotation (not an order).",
        {
            "customer": {"type": "string"},
            "product": {"type": "string"},
            "quantity": {"type": "integer"},
            "unit": {"type": "string", "enum": ["carton", "piece"]},
        },
        ["customer", "product", "quantity", "unit"],
    ),
]
CONFIRM_TOOL = fn(
    "confirm_order",
    "Confirm and commit a customer order for dispatch. Irreversible.",
    {"customer": {"type": "string"}, "product": {"type": "string"}, "quantity": {"type": "integer"}},
    ["customer", "product", "quantity"],
)

PROMPTS = {
    "T2_roman_telugu": "Ravi Traders ki Sunrise sunflower oil 1L 12 cartons quote cheyyi.",
    "T3_telugu_script": "రవి ట్రేడర్స్ కి సన్‌రైజ్ సన్‌ఫ్లవర్ ఆయిల్ 1L 12 కార్టన్లు కోట్ చేయి.",
    "T4_negation": "Ravi Traders ki Sunrise sunflower oil 1L 12 cartons ki quote cheyyi. Order confirm cheyyaku.",
}


def call(client, model, messages, tools=None, **kw):
    t0 = time.perf_counter()
    resp = client.chat.completions.create(model=model, messages=messages, tools=tools, **kw)
    dt = time.perf_counter() - t0
    msg = resp.choices[0].message
    u = resp.usage
    cost = (u.prompt_tokens * PRICE_IN.get(model, 1.25) + u.completion_tokens * PRICE_OUT.get(model, 4.25)) / 1e6
    return {
        "latency_s": round(dt, 2),
        "finish_reason": resp.choices[0].finish_reason,
        "content": msg.content,
        "tool_calls": [
            {"name": tc.function.name, "arguments": tc.function.arguments} for tc in (msg.tool_calls or [])
        ],
        "tokens_in": u.prompt_tokens,
        "tokens_out": u.completion_tokens,
        "cost_usd": round(cost, 6),
        "model": resp.model,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="muse-spark-1.3")
    args = ap.parse_args()
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["meta_api"])
    out = {"model": args.model, "started": datetime.now().isoformat(), "tests": {}}

    def run(name, fn_):
        try:
            out["tests"][name] = fn_()
        except Exception as e:  # record the failure and keep going
            out["tests"][name] = {"error": f"{type(e).__name__}: {e}"}
        print(f"\n== {name}\n{json.dumps(out['tests'][name], ensure_ascii=False, indent=1)[:1500]}")

    sys_msg = {"role": "system", "content": SYSTEM}
    run("T1_basic", lambda: call(client, args.model, [{"role": "user", "content": "Reply with one word: ready"}]))
    run("T2_roman_telugu", lambda: call(client, args.model, [sys_msg, {"role": "user", "content": PROMPTS["T2_roman_telugu"]}], TOOLS))
    run("T3_telugu_script", lambda: call(client, args.model, [sys_msg, {"role": "user", "content": PROMPTS["T3_telugu_script"]}], TOOLS))
    run(
        "T4_negation_x3",
        lambda: [
            call(client, args.model, [sys_msg, {"role": "user", "content": PROMPTS["T4_negation"]}], TOOLS + [CONFIRM_TOOL])
            for _ in range(3)
        ],
    )
    dummy = [
        fn(f"tool_{i:02d}_lookup", f"Dummy lookup tool number {i} for catalog group {i % 8}.", {"q": {"type": "string"}}, ["q"])
        for i in range(37)
    ]
    run("T5_40_tools", lambda: call(client, args.model, [sys_msg, {"role": "user", "content": PROMPTS["T2_roman_telugu"]}], TOOLS + dummy))
    run(
        "T8_determinism_temp0_x3",
        lambda: [
            call(client, args.model, [{"role": "user", "content": "Write a random 12-word sentence about rice."}], temperature=0, seed=7)["content"]
            for _ in range(3)
        ],
    )

    path = ROOT / "artifacts" / "smoke" / f"text_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved {path}")


if __name__ == "__main__":
    main()
