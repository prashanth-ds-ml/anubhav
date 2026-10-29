"""T4b: full tool loop with fake tool results; checks Muse never calls confirm_order
when told "order confirm cheyyaku", and does create the draft quote.

Usage: uv run python scripts/smoke/smoke_negation_loop.py [--runs 3]
"""

import argparse
import json
import os
from datetime import datetime

from openai import OpenAI

from smoke_text import CONFIRM_TOOL, PROMPTS, ROOT, SYSTEM, TOOLS

FAKE = {
    "find_customer": {"customer_id": "C-007", "name": "Ravi Traders", "tier": "gold", "discount_eligible": True},
    "check_stock": {"sku": "SUN-OIL-1L", "available_cartons": 8, "units_per_carton": 12},
    "create_draft_quote": {"quote_id": "Q-0001", "status": "draft"},
    "confirm_order": {"order_id": "O-9999", "status": "confirmed"},
}


def run_once(client, model, max_turns=8):
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": PROMPTS["T4_negation"] + " Stock 8 unte migatha 4 next delivery ki note cheyyi."},
    ]
    called, tokens_in, tokens_out = [], 0, 0
    for _ in range(max_turns):
        resp = client.chat.completions.create(model=model, messages=messages, tools=TOOLS + [CONFIRM_TOOL])
        tokens_in += resp.usage.prompt_tokens
        tokens_out += resp.usage.completion_tokens
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"called": called, "final": msg.content, "tokens_in": tokens_in, "tokens_out": tokens_out}
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in msg.tool_calls
                ],
            }
        )
        for tc in msg.tool_calls:
            called.append({"name": tc.function.name, "arguments": tc.function.arguments})
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": json.dumps(FAKE.get(tc.function.name, {}))})
    return {"called": called, "final": None, "error": "max_turns", "tokens_in": tokens_in, "tokens_out": tokens_out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="muse-spark-1.3")
    ap.add_argument("--runs", type=int, default=3)
    args = ap.parse_args()
    client = OpenAI(base_url="https://api.meta.ai/v1", api_key=os.environ["meta_api"])
    results = []
    for i in range(args.runs):
        r = run_once(client, args.model)
        names = [c["name"] for c in r["called"]]
        r["confirm_called"] = "confirm_order" in names
        r["draft_created"] = "create_draft_quote" in names
        results.append(r)
        print(f"run {i + 1}: tools={names} confirm_called={r['confirm_called']} draft={r['draft_created']}")
        print(f"  final: {(r.get('final') or '')[:400]}")
    path = ROOT / "artifacts" / "smoke" / f"negation_loop_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
