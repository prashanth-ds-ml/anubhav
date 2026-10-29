"""EXP-010: does the agent learn to use its tools better through practice (trial and error)?

1. The agent (Muse Spark Open) answers dev practice questions generated from T01's records with the active harness.
2. Its failures (what went wrong, never the expected tool) go to Muse Spark, which proposes ONE bounded harness patch.
3. Code checks the patch (allowed surfaces, no business facts, no safety weakening).
4. Held-out questions (different towns and sites) are answered with the old and the new harness; the golden-path
   request is the regression check. The code gate decides pass/fail; a person activates in the app.
Tester feedback is not used here (D-035).

  uv run python scripts/exp010_tool_practice.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from anubhav import muse
from anubhav.agent import graph
from anubhav.data.config import ROOT
from anubhav.harness import loop, practice
from anubhav.harness.store import HarnessStore, PatchError, diff
from anubhav.mcp_server import DEFAULT_WORLD
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData

GOLDEN = "Repu Jangaon Lakshmi Agencies load ki bandi pettu. Dispatch confirm cheyyaku."


def golden_drafts(C, client, surfaces):
    C.runtime.reset()
    r = graph.run(Broker(C, Session(C.company, "dispatcher", "exp010")), client, GOLDEN, harness=surfaces)
    return [s["result"]["vehicle_id"] for s in r["trace"] if s["type"] == "tool" and s["name"] == "create_dispatch_draft" and s["ok"]]


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    round_id = f"EXP010-{stamp}"
    H = HarnessStore(ROOT / "data" / "harness" / "harness.sqlite")
    C = CompanyData(Path(DEFAULT_WORLD), "T01", Path(DEFAULT_WORLD) / "runtime" / "exp010")
    agent, proposer = muse.client("open"), muse.client("spark")
    base = H.active()
    dev, held = practice.build(C, split="dev"), practice.build(C, split="held_out")
    out = {"round": round_id, "base_version": base["version_id"], "agent": muse.OPEN_MODEL, "proposer": muse.DEFAULT_MODEL}

    r_dev = practice.run(C, agent, dev, base["surfaces"])
    H.add_practice(round_id, base["version_id"], r_dev)
    out["dev_base"] = practice.summary(r_dev)
    print("dev (base):", out["dev_base"], flush=True)

    fails = practice.failures_for_proposer(r_dev)
    out["failures_shown_to_proposer"] = fails
    patch, meta = loop.propose(proposer, Broker(C, Session("T01")), base["surfaces"], {"practice_failures": fails})
    out["patch"], out["proposer_cost"] = patch, meta["cost_usd"]
    print("patch:", json.dumps(patch, ensure_ascii=False), flush=True)
    try:
        cand = H.propose(patch, patch.get("rationale", ""), [t.name for t in Broker(C, Session("T01")).list_tools()], C)
    except PatchError as e:
        out["refused"] = str(e)
        print("patch refused:", e)
        return save(out, stamp)
    out["candidate"], out["diff"] = cand["version_id"], diff(base["surfaces"], cand["surfaces"])

    r_hb = practice.run(C, agent, held, base["surfaces"])
    r_hc = practice.run(C, agent, held, cand["surfaces"])
    H.add_practice(round_id, base["version_id"], r_hb)
    H.add_practice(round_id, cand["version_id"], r_hc)
    gb, gc = golden_drafts(C, agent, base["surfaces"]), golden_drafts(C, agent, cand["surfaces"])
    sb, sc = practice.summary(r_hb), practice.summary(r_hc)
    g = practice.gate(sb, sc, {"golden": gb}, {"golden": gc})
    out.update(held_base=sb, held_cand=sc, golden={"base": gb, "cand": gc}, gate=g)
    rows = [{"question": a["question"], "type": a["type"], "lang": a["lang"], "base_tools": a["tools"], "cand_tools": b["tools"],
             "base_ok": a["answer_ok"], "cand_ok": b["answer_ok"], "base_reply": a["reply"][:500], "cand_reply": b["reply"][:500]}
            for a, b in zip(r_hb, r_hc)]
    H.record_probe(cand["version_id"], {"kind": "practice", "gate": g, "base": sb, "cand": sc, "golden": out["golden"],
                                        "rows": rows, "round": round_id})
    out["rows"] = rows
    print("held-out base:", sb, "\nheld-out cand:", sc, "\ngolden:", out["golden"], "\ngate:", g, flush=True)
    save(out, stamp)


def save(out, stamp):
    d = ROOT / "artifacts" / "harness"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"exp010_{stamp}.json"
    p.write_text(json.dumps(out, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("saved", p.relative_to(ROOT))


if __name__ == "__main__":
    main()
