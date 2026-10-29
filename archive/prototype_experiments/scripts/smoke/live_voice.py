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
load_dotenv(ROOT.parents[1] / ".env")  # repo-root .env

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
            import numpy as np
            import sounddevice as sd

            info = sd.query_devices(device if device is not None else sd.default.device[0], "input")
            native = int(info["default_samplerate"])
            print(f"🎧 Mic: {info['name']} @ {native} Hz (resampled to {RATE} Hz)")

            def on_audio(indata, frames, time_info, status):
                mono = indata[:, 0].astype(np.float32)
                if native != RATE:  # resample this chunk to 24 kHz
                    n_out = int(round(len(mono) * RATE / native))
                    mono = np.interp(np.linspace(0, len(mono) - 1, n_out), np.arange(len(mono)), mono)
                loop.call_soon_threadsafe(queue.put_nowait, mono)

            buf = np.zeros(0, dtype=np.float32)
            padded_blocks, last_meter = 0, 0.0
            print(f"🎙️  Speak now ({seconds:.0f} s)… Telugu / Roman Telugu / English all fine.\n")
            with sd.InputStream(samplerate=native, channels=1, dtype="int16", callback=on_audio, device=device):
                start = loop.time()
                sent = 0
                while sent * 0.08 < seconds and not reader.done():
                    # pace: send block k at start + k*80 ms, so ingress is always real-time
                    await asyncio.sleep(max(0.0, start + sent * 0.08 - loop.time()))
                    while not queue.empty():
                        buf = np.concatenate([buf, queue.get_nowait()])
                    if len(buf) >= BLOCK:
                        block, buf = buf[:BLOCK], buf[BLOCK:]
                    else:  # mic stalled: pad with silence rather than starve the server
                        block = np.concatenate([buf, np.zeros(BLOCK - len(buf), dtype=np.float32)])
                        buf = np.zeros(0, dtype=np.float32)
                        padded_blocks += 1
                    pcm = np.clip(block, -32768, 32767).astype("<i2").tobytes()
                    recorded += pcm
                    await ws.send(pcm)
                    sent += 1
                    if not last_partial and loop.time() - last_meter > 0.3:
                        level = min(20, int(np.sqrt(np.mean(block**2)) / 300))
                        print(f"\r🎚️  mic level {'▮' * level}{'·' * (20 - level)}", end="", flush=True)
                        last_meter = loop.time()
            if padded_blocks > sent * 0.2:
                print(f"\n⚠️  Mic delivered little audio ({padded_blocks}/{sent} blocks padded). Try --list-devices / --device N.")

        if not reader.done():
            await ws.send(json.dumps({"type": "endStream"}))
        await reader  # re-raises a server error, if any

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
    ap.add_argument("--list-devices", action="store_true", help="show microphones and exit")
    args = ap.parse_args()

    if args.list_devices:
        import sounddevice as sd

        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] > 0:
                default = " (default)" if i == sd.default.device[0] else ""
                print(f"{i:3d}  {d['name']}  [{sd.query_hostapis(d['hostapi'])['name']}, {int(d['default_samplerate'])} Hz]{default}")
        return

    try:
        res = asyncio.run(transcribe_live(args.seconds, args.file, args.device))
    except RuntimeError as e:
        print(f"\n❌ Transcription failed: {e}")
        sys.exit(1)
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
