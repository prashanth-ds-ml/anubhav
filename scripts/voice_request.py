"""Voice path: a planner's voice note -> Muse Voice Transcribe -> (planner confirms the transcript) -> the agent.

  uv run python scripts/voice_request.py --wav voice/note.wav --company T01               # transcribe + run the agent
  uv run python scripts/voice_request.py --wav voice/note.wav --transcribe-only
The WAV must be mono 16-bit PCM at 16 or 24 kHz (convert with: ffmpeg -i in.m4a -ac 1 -ar 24000 -sample_fmt s16 out.wav).
Site and town names from the company's master are passed as keywords so they're spelled right."""

import argparse
import sys
from pathlib import Path

from anubhav import muse, trace
from anubhav.agent import graph
from anubhav.mcp_server import DEFAULT_WORLD
from anubhav.runtime.broker import Broker, Session
from anubhav.runtime.company import CompanyData


def keywords(C, limit=40):
    names = sorted({s["town"] for s in C.sites.values()}) + sorted({s["name"] for s in C.sites.values()})
    return names[:limit]


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--company", default="T01")
    ap.add_argument("--model", choices=["open", "spark"], default="open")
    ap.add_argument("--world", default=str(DEFAULT_WORLD))
    ap.add_argument("--transcribe-only", action="store_true")
    ap.add_argument("--yes", action="store_true", help="skip the transcript confirmation")
    a = ap.parse_args(argv)
    C = CompanyData(Path(a.world), a.company, Path(a.world) / "runtime" / "voice")
    t = muse.transcribe(Path(a.wav), keywords=keywords(C))
    print(f"Transcript ({t['audio_ms'] / 1000:.1f}s audio, {t['latency_s']}s, ${t['cost_usd']}): {t['transcript']}")
    if a.transcribe_only or not t["transcript"]:
        return
    if not a.yes and input("Use this transcript? [y/N] ").strip().lower() != "y":
        return
    r = graph.run(Broker(C, Session(a.company, "dispatcher", "voice")), muse.client(a.model), t["transcript"])
    r["voice"] = {"wav": Path(a.wav).name, **t}
    trace.save(r, label="voice")
    print(f"Reply: {r['reply']}\nDrafts: {r['drafts']} · ${r['cost_usd'] + t['cost_usd']:.4f} · run {r['run_id']}")


if __name__ == "__main__":
    main()
