// The transcription service wants 16 kHz mono WAV. Browsers record compressed audio, so convert it here.

export const RATE = 16000;
export const MAX_SECONDS = 30;

/** Encode mono float samples (-1..1) as a 16-bit PCM WAV file. */
export function encodeWav(samples: Float32Array, rate = RATE): ArrayBuffer {
  const buf = new ArrayBuffer(44 + samples.length * 2);
  const v = new DataView(buf);
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + samples.length * 2, true); str(8, "WAVE");
  str(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, samples.length * 2, true);
  samples.forEach((s, i) => v.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, s)) * 32767), true));
  return buf;
}

/** Decode a recorded blob (webm/ogg/mp4), downmix to mono and resample to 16 kHz, then encode as WAV. */
export async function toWav16k(blob: Blob): Promise<ArrayBuffer> {
  const ctx = new AudioContext();
  try {
    const decoded = await ctx.decodeAudioData(await blob.arrayBuffer());
    const frames = Math.min(Math.ceil(decoded.duration * RATE), MAX_SECONDS * RATE);
    const off = new OfflineAudioContext(1, Math.max(frames, 1), RATE); // rendering to 1 channel downmixes
    const src = off.createBufferSource();
    src.buffer = decoded;
    src.connect(off.destination);
    src.start();
    return encodeWav((await off.startRendering()).getChannelData(0));
  } finally {
    void ctx.close();
  }
}
