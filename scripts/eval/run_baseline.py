"""Baseline runs (EXP-001/002): a frozen Muse agent on the benchmark, graded against the answer key.

Arms (same system prompt, same grader; only the tool setup differs):
  core  8 core tools, Chat Completions (B0, the first baseline)
  a     all 40 tools passed directly, Chat Completions
  b     all 40 tools deferred in namespaces, Muse hosted tool search, Responses API
Each run uses a freshly reset DB. No shop-specific hints: the frozen model with a generic harness.

Usage:
  uv run python scripts/eval/run_baseline.py --arm b --tasks D01 D09
  uv run python scripts/eval/run_baseline.py --arm a --all --repeats 2 --workers 4
"""

import argparse
import json
import re
import sys
import tempfile
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from order_agent import agent, db, tools  # noqa: E402
from order_agent.llm import MuseClient  # noqa: E402

TASKS = ROOT / "datasets" / "tasks" / "benchmark_v1.jsonl"
DEFAULT_TASKS = ["D01", "D09", "D16", "D19", "D28"]


def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[\s,.;:!?()/-]+", text.lower()) if t]


def run_task(arm, client, model, task):
    with tempfile.TemporaryDirectory() as tmp:
        conn = db.connect(db.reset(Path(tmp) / "business.db"))
        if arm == "b":
            run = agent.run_responses(conn, task["request"], client, model)
        else:
            run = agent.run_chat(conn, task["request"], client, tools.CORE if arm == "core" else None)
        quotes = [dict(q) for q in conn.execute("SELECT * FROM quotes")]
        lines = [dict(sku=r["sku"], cases=r["cases"]) for r in conn.execute("SELECT sku, cases FROM quote_lines")]
        conn.close()
    verdict, why = grade(task["expected"], quotes, lines)
    if run.hit_turn_limit:
        why += " (hit turn limit)"
    return {"id": task["id"], "split": task["split"], "lang": task["lang"], "tags": task["tags"],
            "request": task["request"], "pass": verdict, "why": why, "unsafe": unsafe(task["expected"], quotes),
            "lang_ok": reply_language_ok(task["lang"], run.final), "final_reply": run.final, "quotes": quotes,
            "quote_lines": lines, "tool_calls": len(run.trace), "tools_used": [s["tool"] for s in run.trace],
            "searches": run.searches, "trace": run.trace, "turns": run.turns, "cost_usd": round(run.cost_usd, 5),
            "tokens_in": run.tokens_in, "tokens_out": run.tokens_out, "latency_s": round(run.latency_s, 2)}


HINDI = {"hai", "hain", "ke", "liye", "gaya", "banaya", "aapka", "kar", "diya", "mein", "kya", "chahiye", "hoga"}


def reply_language_ok(lang: str, reply: str) -> bool:
    """Telugu tasks need Telugu script; no task should get Devanagari or Hindi-style Roman text."""
    if re.search(r"[ऀ-ॿ]", reply):
        return False
    if sum(w in HINDI for w in tokens(reply)) >= 2:
        return False
    return bool(re.search(r"[ఀ-౿]", reply)) if lang == "te" else True


def unsafe(exp, quotes) -> bool:
    """A quote that should not exist, or one for the wrong customer."""
    if exp["action"] != "quote":
        return bool(quotes)
    return any(q["customer_id"] != exp["customer_id"] for q in quotes)


def grade(exp, quotes, lines):
    if exp["action"] != "quote":
        return (not quotes, "no quote, as expected" if not quotes else f"created {len(quotes)} quote(s); expected {exp['action']}")
    if len(quotes) != 1:
        return False, f"expected 1 quote, got {len(quotes)}"
    if quotes[0]["customer_id"] != exp["customer_id"]:
        return False, f"customer {quotes[0]['customer_id']} != {exp['customer_id']}"
    got = sorted((line["sku"], line["cases"]) for line in lines)
    want = sorted((line["sku"], line["cases"]) for line in exp["lines"])
    if got != want:
        return False, f"lines {got} != {want}"
    return True, "lines and customer match"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=DEFAULT_TASKS)
    ap.add_argument("--all", action="store_true", help="run every task in the benchmark")
    ap.add_argument("--split", choices=["dev", "heldout"], help="with --all, only this split")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--model", default="muse-spark-1.3")
    ap.add_argument("--arm", choices=["core", "a", "b"], default="a")
    args = ap.parse_args()

    tasks = {t["id"]: t for t in map(json.loads, TASKS.read_text(encoding="utf-8").splitlines())}
    ids = [t for t in tasks if not args.split or tasks[t]["split"] == args.split] if args.all else args.tasks
    client = agent.responses_client() if args.arm == "b" else MuseClient(model=args.model)
    jobs = [(tid, rep) for rep in range(args.repeats) for tid in ids]

    def job(item):
        tid, rep = item
        try:
            res = run_task(args.arm, client, args.model, tasks[tid])
        except Exception as e:  # API failure: log it as inconclusive, never as a pass
            res = {"id": tid, "split": tasks[tid]["split"], "lang": tasks[tid]["lang"], "tags": tasks[tid]["tags"],
                   "request": tasks[tid]["request"], "pass": False, "why": f"ERROR {type(e).__name__}: {e}",
                   "error": True, "unsafe": False, "lang_ok": True, "tool_calls": 0, "trace": [],
                   "cost_usd": 0.0, "latency_s": 0.0, "final_reply": ""}
        res["repeat"] = rep
        mark = "⚠️" if res.get("error") else ("✅" if res["pass"] else "❌")
        print(f"{mark} {tid}#{rep} [{res['lang']}] {res['why'][:120]} · {res['tool_calls']} calls · ${res['cost_usd']}", flush=True)
        return res

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(job, jobs))

    summary = summarize(results, args.repeats)
    print_summary(summary)
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    out = ROOT / "artifacts" / "baseline" / f"arm-{args.arm}_{stamp}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"arm": args.arm, "model": args.model, "repeats": args.repeats, "summary": summary, "results": results},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Results saved: {out.relative_to(ROOT)}")


def summarize(results, repeats):
    by_task = defaultdict(list)
    for r in results:
        by_task[r["id"]].append(r)
    task_rate = {tid: sum(r["pass"] for r in rs) / len(rs) for tid, rs in by_task.items()}
    groups = defaultdict(list)
    for tid, rs in by_task.items():
        r0 = rs[0]
        for key in [f"split:{r0['split']}", f"lang:{r0['lang']}", *(f"tag:{t}" for t in r0["tags"])]:
            groups[key].append(task_rate[tid])
    n = len(results)
    return {
        "tasks": len(by_task), "runs": n, "repeats": repeats,
        "mean_success": round(sum(r["pass"] for r in results) / n, 3),
        "pass_all_repeats": sum(rate == 1 for rate in task_rate.values()),
        "fail_all_repeats": sum(rate == 0 for rate in task_rate.values()),
        "flaky": sorted(tid for tid, rate in task_rate.items() if 0 < rate < 1),
        "failing": sorted(tid for tid, rate in task_rate.items() if rate < 1),
        "errors": sum(bool(r.get("error")) for r in results),
        "unsafe_runs": sum(r["unsafe"] for r in results),
        "lang_ok_rate": round(sum(r["lang_ok"] for r in results) / n, 3),
        "cost_usd": round(sum(r["cost_usd"] for r in results), 4),
        "mean_tool_calls": round(sum(r["tool_calls"] for r in results) / n, 1),
        "mean_latency_s": round(sum(r["latency_s"] for r in results) / n, 1),
        "mean_tokens_in": round(sum(r.get("tokens_in", 0) for r in results) / n),
        "groups": {k: {"tasks": len(v), "success": round(sum(v) / len(v), 2)} for k, v in sorted(groups.items())},
        "why_failed": {f"{r['id']}#{r['repeat']}": r["why"] for r in results if not r["pass"]},
    }


def print_summary(s):
    print(f"\n=== {s['tasks']} tasks × {s['repeats']} = {s['runs']} runs ===")
    print(f"Mean success {s['mean_success']:.0%} · pass every repeat {s['pass_all_repeats']} · "
          f"fail every repeat {s['fail_all_repeats']} · flaky {len(s['flaky'])}")
    print(f"Unsafe runs {s['unsafe_runs']} · reply language OK {s['lang_ok_rate']:.0%} · errors {s['errors']}")
    print(f"Cost ${s['cost_usd']} · {s['mean_tool_calls']} tool calls, {s['mean_tokens_in']} input tokens "
          f"and {s['mean_latency_s']} s per run")
    for k, g in s["groups"].items():
        print(f"  {k:24} {g['success']:>5.0%}  ({g['tasks']} tasks)")
    print("Failing:", ", ".join(s["failing"]) or "none")


if __name__ == "__main__":
    main()
