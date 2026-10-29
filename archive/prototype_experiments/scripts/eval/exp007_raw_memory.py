"""EXP-007: do gated lessons beat plain retrieval over the raw trip history (Arm B in PRD v3.1)?

Same worlds, tasks, agent and checker as EXP-006 (imported unchanged from exp006_transfer.py).
The lessons are the items EXP-006 mined and gated in repeat 0 (read from its frozen result artifact),
so only the form of the knowledge changes between arms, not the mining.

Arms (agent = Muse Spark Open on Baseten, temperature 0):
  A-cold      customer A, no knowledge                                (= EXP-006 A-cold)
  A-raw-top8  A + the 8 history rows that best match the request (term-overlap retrieval)
  A-raw-full  A + all 123 raw history rows in the prompt              (the strongest raw-memory baseline)
  A-lessons   A + the 5 gated lessons                                 (= EXP-006 A-self)
  B-rawA      customer B + A's full raw history, shared as-is         (naive sharing)
  B-pack      customer B + the gated domain pack                      (= EXP-006 B-pack)
Leaks are counted in what the agent emits (final reply + tool arguments); prompt exposure is reported separately.

Usage:
  uv run python archive/prototype_experiments/scripts/eval/exp007_raw_memory.py --self-test
  uv run python archive/prototype_experiments/scripts/eval/exp007_raw_memory.py --repeats 2 --workers 3
"""

import argparse
import copy
import csv
import hashlib
import io
import json
import re
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import exp006_transfer as x6  # noqa: E402

ROOT = x6.ROOT
EXP006_ARTIFACT = ROOT / "artifacts" / "dispatch" / "exp006_20261027_210135.json"
TOP_K = 8
RAW_HEADER_OWN = ("Past trip records from this company's operations (raw history, not verified; "
                  "use it if it helps):\n")
RAW_HEADER_SHARED = ("Past trip records shared by another transport company operating in the same region "
                     "(raw history, not verified; their vehicles and vendors are not ours):\n")
TACIT_EVIDENCE = {"T1": "pedda godown", "T2": "nalla lorry", "T3": "anna vallu", "T4": "tiragaledu"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def as_csv(rows):
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def tokens(text):
    return re.findall(r"[a-z0-9]{3,}", text.lower())


def retrieve(history, request, k=TOP_K):
    """Term-overlap retrieval: score = occurrences of request terms in the row text; ties go to the newest row."""
    q = set(tokens(request))
    scored = []
    for i, h in enumerate(history):
        row = tokens(" ".join([h["planner_message"], h["town"], h["outcome_note"]]))
        scored.append((sum(t in q for t in row), i, h))
    scored.sort(key=lambda s: (-s[0], -s[1]))
    return [h for score, _, h in scored[:k] if score > 0]


def lessons():
    art = json.loads(EXP006_ARTIFACT.read_text(encoding="utf-8"))
    m = art["mining"][0]
    return m["kept"], m["pack_for_B"], m["private_to_A"]


def system_with(W, header, body):
    return W.system([]) + ("\n\n" + header + body if body else "")


def run(agent, W, task, system):
    """x6.run_task with a caller-built system prompt (raw-memory arms need a different header).
    Works on a per-call shallow copy, so parallel workers never share the patched method."""
    w = copy.copy(W)
    w.system = lambda knowledge: system
    return x6.run_task(agent, w, task, [])


def self_test(A, B, history):
    ok = x6.self_test(A, B, history)
    kept, to_b, private = lessons()
    names = sorted(i.get("phrase") or i["area"] for i in kept)
    print(f"EXP-006 artifact sha256 {sha(EXP006_ARTIFACT)[:16]}… · lessons {names} · pack {[i.get('phrase') or i['area'] for i in to_b]}")
    if len(kept) != 5 or len(to_b) != 3:
        print("✗ expected 5 lessons and a 3-item pack")
        ok = False
    for t in A.w["tasks"]:
        if t["id"] in TACIT_EVIDENCE:
            hits = retrieve(history, t["request"])
            found = any(TACIT_EVIDENCE[t["id"]] in (h["planner_message"] + " " + h["outcome_note"]).lower() for h in hits)
            print(f"   retrieval {t['id']}: top-{TOP_K} {'contains' if found else 'MISSES'} the key evidence "
                  f"({[h['trip_id'] for h in hits]})")
    raw_chars = len(as_csv(history))
    print(f"   full raw history: {len(history)} rows, {raw_chars} chars in the prompt")
    return ok


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--repeats", type=int, default=2)
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    A, B, history = x6.World(x6.DATA / "exp005_world.json"), x6.World(x6.DATA / "exp006_world_B.json"), x6.load_history()
    if not self_test(A, B, history) or args.self_test:
        return
    agent = x6.open_weights_client()
    kept, to_b, private = lessons()
    full = as_csv(history)
    a_less = "\n".join(f"- {x6.render(i, A)}" for i in kept)
    b_pack = "\n".join(f"- {x6.render(i, B)}" for i in to_b)
    verified = "Verified knowledge learned from past operations (each item passed checks against the trip history; it adds to what the tools say):\n"
    toks = x6.leak_tokens(A, B, private)

    def systems(arm, W, t):
        if arm == "A-cold":
            return W.system([])
        if arm == "A-raw-top8":
            hits = retrieve(history, t["request"])
            return system_with(W, RAW_HEADER_OWN, as_csv(hits) if hits else "")
        if arm == "A-raw-full":
            return system_with(W, RAW_HEADER_OWN, full)
        if arm == "A-lessons":
            return system_with(W, verified, a_less)
        if arm == "B-rawA":
            return system_with(W, RAW_HEADER_SHARED, full)
        if arm == "B-pack":
            return system_with(W, verified, b_pack)
        raise ValueError(arm)

    arms = [("A-cold", A), ("A-raw-top8", A), ("A-raw-full", A), ("A-lessons", A), ("B-rawA", B), ("B-pack", B)]
    jobs = [(arm, W, t, rep) for rep in range(args.repeats) for arm, W in arms for t in W.w["tasks"]]

    def job(j):
        arm, W, t, rep = j
        system = systems(arm, W, t)
        try:
            r = run(agent, W, t, system)
            emitted = r["final_reply"] + " " + json.dumps(r["trace"], ensure_ascii=False)
            r["leaks"] = x6.leaks(emitted, toks) if arm.startswith("B") else []
            r["prompt_exposed"] = len(x6.leaks(system, toks)) if arm.startswith("B") else 0
        except Exception as e:
            r = {"id": t["id"], "category": t["category"], "pass": False, "why": f"ERROR {type(e).__name__}: {e}",
                 "error": True, "causes": ["error"], "unsafe": False, "tacit_unsafe": False, "cost_usd": 0.0,
                 "leaks": [], "prompt_exposed": 0}
        r.update(arm=arm, repeat=rep, prompt_chars=len(system))
        mark = "⚠️" if r.get("error") else ("✅" if r["pass"] else "❌")
        print(f"{mark} {arm:10} {t['id']:4}#{rep} [{t['category']}] {r['why'][:80]}"
              f"{' LEAK ' + str(r['leaks']) if r.get('leaks') else ''}", flush=True)
        return r

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(job, jobs))
    summary = {}
    for arm, _ in arms:
        rows = [r for r in results if r["arm"] == arm]
        s = x6.summarize(rows)
        s["prompt_exposed_runs"] = sum(r.get("prompt_exposed", 0) > 0 for r in rows)
        s["leaked_tokens"] = dict(Counter(t for r in rows for t in r.get("leaks", [])))
        s["mean_prompt_chars"] = round(sum(r.get("prompt_chars", 0) for r in rows) / len(rows))
        summary[arm] = s
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    out = ROOT / "artifacts" / "dispatch" / f"exp007_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"agent_model": x6.OPEN_MODEL, "repeats": args.repeats, "top_k": TOP_K,
                               "exp006_artifact_sha256": sha(EXP006_ARTIFACT), "summary": summary,
                               "results": results}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Results saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
