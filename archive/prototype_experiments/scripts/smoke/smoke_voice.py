"""T6: transcribe self-recorded Telugu voice notes with Muse Voice Transcribe.

Any audio format works (ffmpeg converts to mono 16-bit PCM WAV @ 24 kHz first).
Usage: uv run python scripts/smoke/smoke_voice.py voice/*.m4a [--keywords "Ravi Traders,Sunrise"]
"""

import argparse
import json
import os
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT.parents[1] / ".env")  # repo-root .env
URL = "https://api.meta.ai/v1/asr/transcribe"


def to_wav(src: Path, dst: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-ac", "1", "-ar", "24000", "-sample_fmt", "s16", str(dst)],
        check=True,
    )


def transcribe(wav: Path, keywords: list[str], language_bias: list[str]):
    settings = {"mode": "PUSH_TO_TALK", "model": "muse-voice-transcribe-1.0", "audioEncoding": "WAV"}
    if language_bias:
        settings["languageBias"] = language_bias
    if keywords:
        settings["keywords"] = keywords
    t0 = time.perf_counter()
    with wav.open("rb") as f:
        r = httpx.post(
            URL,
            headers={"Authorization": f"Bearer {os.environ['meta_api']}", "Accept": "application/json"},
            files={
                "request": (None, json.dumps(settings), "application/json"),
                "audio": (wav.name, f, "audio/wav"),
            },
            timeout=120,
        )
    dt = time.perf_counter() - t0
    r.raise_for_status()
    body = r.json()
    return {"latency_s": round(dt, 2), "transcript": body.get("transcript"), "audio_ms": body.get("audioDurationMs")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--keywords", default="")
    ap.add_argument("--bias", default="Telugu,English")
    args = ap.parse_args()
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()]
    bias = [b.strip() for b in args.bias.split(",") if b.strip()]
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for f in map(Path, args.files):
            wav = Path(tmp) / (f.stem + ".wav")
            to_wav(f, wav)
            for label, kw, lb in [("plain", [], []), ("biased", keywords, bias)]:
                try:
                    res = transcribe(wav, kw, lb)
                except Exception as e:
                    res = {"error": f"{type(e).__name__}: {e}"}
                res.update(file=f.name, variant=label)
                results.append(res)
                print(json.dumps(res, ensure_ascii=False))
    path = ROOT / "artifacts" / "smoke" / f"voice_{datetime.now():%Y%m%d_%H%M%S}.json"
    path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved {path}")


if __name__ == "__main__":
    main()
