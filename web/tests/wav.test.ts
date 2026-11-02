import { describe, it, expect } from "vitest";
import { encodeWav } from "../src/lib/wav";

describe("encodeWav", () => {
  const wav = encodeWav(new Float32Array([0, 1, -1, 0.5]));
  const v = new DataView(wav);
  const tag = (o: number) => String.fromCharCode(v.getUint8(o), v.getUint8(o + 1), v.getUint8(o + 2), v.getUint8(o + 3));

  it("writes a valid 16 kHz mono 16-bit PCM header", () => {
    expect([tag(0), tag(8), tag(12), tag(36)]).toEqual(["RIFF", "WAVE", "fmt ", "data"]);
    expect(v.getUint16(20, true)).toBe(1); // PCM
    expect(v.getUint16(22, true)).toBe(1); // mono
    expect(v.getUint32(24, true)).toBe(16000);
    expect(v.getUint16(34, true)).toBe(16);
    expect(v.getUint32(40, true)).toBe(8); // 4 samples x 2 bytes
    expect(v.getUint32(4, true)).toBe(wav.byteLength - 8);
  });
  it("converts samples and clips out-of-range values", () => {
    expect([0, 1, 2, 3].map((i) => v.getInt16(44 + i * 2, true))).toEqual([0, 32767, -32767, 16384]);
    const clipped = new DataView(encodeWav(new Float32Array([5, -5])));
    expect([clipped.getInt16(44, true), clipped.getInt16(46, true)]).toEqual([32767, -32767]);
  });
  it("30 seconds stays under the server's size limit", () => {
    expect(encodeWav(new Float32Array(16000 * 30)).byteLength).toBeLessThan(2_000_000);
  });
});
