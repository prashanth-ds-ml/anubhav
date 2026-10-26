"""Live voice transcription test with Muse Voice Transcribe (realtime WebSocket).

Speak into the mic; partial transcripts print live. The recording is saved to voice/
(gitignored) so it can be re-used for free in later tests, and the cost is logged.

Usage:
  uv run python scripts/smoke/live_voice.py                 # 15 s from default mic
  uv run python scripts/smoke/live_voice.py --seconds 20 --agent   # also send transcript to Muse with tools
  uv run python scripts/smoke/live_voice.py --file voice/x.wav     # stream a 24 kHz mono WAV instead of the mic
"""

import argparse
import asyncio
import json
import os
import sys
import uuid
import wave
from datetime import datetime
from pathlib import Path

import websockets
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

MODEL = "muse-voice-transcribe-1.0"
PRICE_PER_HOUR = 0.18
RATE = 24_000
BLOCK = RATE * 80 // 1000  # 80 ms per frame
KEYWORDS = ["Ravi Traders", "Godavari Gold", "Konaseema", "Kakatiya", "Deccan Pure", "sunflower oil", "cartons", "quote"]


async def transcribe_live(seconds: float, wav_in: Path | None, device: int | None) -> dict:
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    recorded = bytearray()
    final_text, last_partial, processed_ms = [], "", 0

    uri = f"wss://api.meta.ai/v1/asr/realtime?sessionId=live-{uuid.uuid4()}"
    async with websockets.connect(uri, open_timeout=30, max_size=None) as ws:
        await ws.send(
            json.dumps(
                {
                    "authorization": {"accessToken": f"Bearer {os.environ['meta_api']}"},
                    "audioEncoding": "PCM_24KHZ",
                    "model": MODEL,
                    "mode": "PUSH_TO_TALK",
                    "partialMode": "CUMULATIVE",
                    "emitAudioProgress": False,
                    "languageBias": ["Telugu", "English"],
                    "keywords": KEYWORDS,
                }
            )
        )
        ack = json.loads(await ws.recv())
        if "sessionId" not in ack:
            raise RuntimeError(f"Handshake failed: {ack}")

        async def read_events():
            nonlocal last_partial, processed_ms
            async for msg in ws:
                if isinstance(msg, bytes):
                    continue
                ev = json.loads(msg)
                kind = ev.get("type")
                if kind == "error":
                    raise RuntimeError(ev.get("message"))
                if kind == "transcript":
                    processed_ms = ev.get("audioProcessedMs", processed_ms)
                    if ev.get("final"):
                        final_text.append(ev["transcript"])
                        print(f"\r✅ {ev['transcript']}{' ' * 20}", flush=True)
                    else:
                        last_partial = ev["transcript"]
                        print(f"\r… {last_partial[-110:]}", end="", flush=True)

        reader = asyncio.create_task(read_events())

        if wav_in:
            with wave.open(str(wav_in), "rb") as w:
                assert w.getframerate() == RATE and w.getnchannels() == 1 and w.getsampwidth() == 2, "need 24 kHz mono 16-bit"
                while chunk := w.readframes(BLOCK):
                    recorded += chunk
                    await ws.send(chunk)
                    await asyncio.sleep(0.08)  # pace at real time
        else:
            import sounddevice as sd

            def on_audio(indata, frames, time_info, status):
                loop.call_soon_threadsafe(queue.put_nowait, bytes(indata))

            print(f"🎙️  Speak now ({seconds:.0f} s)… Telugu / Roman Telugu / English all fine.\n")
            with sd.RawInputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=BLOCK, callback=on_audio, device=device):
                deadline = loop.time() + seconds
                while loop.time() < deadline:
                    chunk = await queue.get()
                    recorded += chunk
                    await ws.send(chunk)
            while not queue.empty():
                chunk = queue.get_nowait()
                recorded += chunk
                await ws.send(chunk)

        await ws.send(json.dumps({"type": "endStream"}))
        await reader

    transcript = " ".join(final_text) or last_partial
    audio_s = len(recorded) / 2 / RATE
    return {"transcript": transcript, "audio_s": round(audio_s, 2), "recorded": bytes(recorded)}


def run_agent_check(transcript: str) -> dict:
    """Send the transcript to Muse with the smoke-test tools; report which tools it calls."""
    sys.path.insert(0, str(Path(__file__).parent))
    from smoke_text import SYSTEM, TOOLS

    sys.path.insert(0, str(ROOT / "src"))
    from order_agent.llm import MuseClient

    r = MuseClient().chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": transcript}], TOOLS)
    return {
        "tool_calls": [{"name": t.name, "arguments": t.arguments} for t in r.tool_calls],
        "content": r.content,
        "cost_usd": round(r.cost_usd, 5),
        "latency_s": r.latency_s,
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")  # Telugu + emoji in the Windows/VS Code terminal
    ap = argparse.ArgumentParser()
    ap.add_argument("--seconds", type=float, default=15)
    ap.add_argument("--file", type=Path)
    ap.add_argument("--device", type=int)
    ap.add_argument("--agent", action="store_true", help="also send transcript to Muse Spark with tools")
    ap.add_argument("--label", default="live")
    args = ap.parse_args()

    res = asyncio.run(transcribe_live(args.seconds, args.file, args.device))
    stamp = f"{datetime.now():%Y%m%d_%H%M%S}"
    if not args.file:
        out_wav = ROOT / "voice" / f"{args.label}_{stamp}.wav"
        out_wav.parent.mkdir(exist_ok=True)
        with wave.open(str(out_wav), "wb") as w:
            w.setnchannels(1), w.setsampwidth(2), w.setframerate(RATE), w.writeframes(res["recorded"])
        print(f"\n💾 Saved recording: {out_wav.relative_to(ROOT)}")

    cost = res["audio_s"] / 3600 * PRICE_PER_HOUR
    record = {
        "time": stamp,
        "label": args.label,
        "source": str(args.file) if args.file else "mic",
        "audio_s": res["audio_s"],
        "transcript": res["transcript"],
        "transcribe_cost_usd": round(cost, 6),
    }
    print(f"\n📝 Transcript: {res['transcript']}")
    print(f"⏱️  Audio: {res['audio_s']} s → transcription cost ≈ ${cost:.5f}")

    if args.agent and res["transcript"]:
        record["agent"] = run_agent_check(res["transcript"])
        print(f"🛠️  Muse tool calls: {[t['name'] + t['arguments'] for t in record['agent']['tool_calls']]}")
        print(f"💬 Muse says: {record['agent']['content']}")
        print(f"💰 Agent cost ≈ ${record['agent']['cost_usd']}")

    log = ROOT / "artifacts" / "smoke" / "voice_log.jsonl"
    with log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(f"📒 Logged to {log.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
