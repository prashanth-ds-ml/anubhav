import { useEffect, useRef, useState } from "react";
import { Mic as MicIcon, Square, Loader2, RotateCcw } from "lucide-react";
import { sendVoice } from "../lib/api";
import { MAX_SECONDS, toWav16k } from "../lib/wav";

type State =
  | { kind: "idle" }
  | { kind: "recording"; secs: number }
  | { kind: "busy" }
  | { kind: "error"; message: string; retry: boolean };

const supported = () => typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";

export function Mic({ available, reason, onTranscript }: {
  available: boolean;
  reason: string | null;
  onTranscript: (text: string, meta: string) => void;
}) {
  const [state, setState] = useState<State>({ kind: "idle" });
  const rec = useRef<MediaRecorder | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const lastWav = useRef<ArrayBuffer | null>(null);
  const can = available && supported();

  useEffect(() => () => { clearInterval(timer.current); rec.current?.stream.getTracks().forEach((t) => t.stop()); }, []);

  async function transcribe(wav: ArrayBuffer) {
    setState({ kind: "busy" });
    const r = await sendVoice(wav);
    if (r.ok) {
      lastWav.current = null;
      setState({ kind: "idle" });
      onTranscript(r.transcript, `Heard ${(r.audio_ms / 1000).toFixed(1)} s of audio ($${r.cost_usd.toFixed(4)}). Fix anything misheard, then press Send.`);
    } else {
      // The recording is kept so a network or service hiccup can be retried without speaking again.
      const retry = ["TRANSCRIBE_FAILED", "NETWORK"].includes(r.code);
      if (!retry) lastWav.current = null;
      setState({ kind: "error", message: r.message, retry });
    }
  }

  async function start() {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      const name = (e as DOMException).name;
      setState({
        kind: "error", retry: false,
        message: name === "NotFoundError"
          ? "No microphone was found. Type your request instead."
          : "Microphone access was blocked. Allow it in your browser's site settings, or type your request instead.",
      });
      return;
    }
    const chunks: Blob[] = [];
    const mr = new MediaRecorder(stream);
    rec.current = mr;
    mr.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      clearInterval(timer.current);
      try {
        lastWav.current = await toWav16k(new Blob(chunks, { type: mr.mimeType }));
      } catch {
        return setState({ kind: "error", message: "That recording could not be read. Try again.", retry: false });
      }
      void transcribe(lastWav.current);
    };
    mr.start();
    setState({ kind: "recording", secs: 0 });
    timer.current = window.setInterval(() => {
      setState((s) => {
        if (s.kind !== "recording") return s;
        if (s.secs + 1 >= MAX_SECONDS) mr.state === "recording" && mr.stop();
        return { kind: "recording", secs: s.secs + 1 };
      });
    }, 1000);
  }

  const stop = () => rec.current?.state === "recording" && rec.current.stop();
  const recording = state.kind === "recording";

  return (
    <div className="mic">
      <button
        type="button"
        className={`micbtn ${recording ? "recording" : ""}`}
        disabled={!can || state.kind === "busy"}
        aria-pressed={recording}
        aria-label={recording ? "Stop recording" : "Record a voice message"}
        title={can ? undefined : available ? "Voice is off: this browser cannot record audio." : reason ?? undefined}
        onClick={recording ? stop : start}
      >
        {state.kind === "busy" ? <Loader2 size={20} className="spin" aria-hidden /> : recording ? <Square size={20} aria-hidden /> : <MicIcon size={20} aria-hidden />}
        {recording && <span className="mono">{state.secs}s / {MAX_SECONDS}s</span>}
      </button>
      <div className="small mic-status" role="status" aria-live="polite">
        {!can && <span className="muted">{available ? "Voice is off: this browser cannot record audio." : reason}</span>}
        {can && state.kind === "busy" && <span>Turning speech into text…</span>}
        {can && recording && <span>Recording… press the button to stop.</span>}
        {state.kind === "error" && (
          <span className="err-text">
            {state.message}{" "}
            {state.retry && lastWav.current && (
              <button type="button" className="linklike" onClick={() => void transcribe(lastWav.current!)}>
                <RotateCcw size={12} aria-hidden /> Try again
              </button>
            )}
          </span>
        )}
        {can && state.kind === "idle" && <span className="muted">Audio goes to Meta's transcription service to become text. Anubhav doesn't store it.</span>}
      </div>
    </div>
  );
}
