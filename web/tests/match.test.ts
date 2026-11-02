import { describe, it, expect } from "vitest";
import { closest } from "../src/lib/match";

const P = [
  "Plan a truck for tomorrow's Lakshmi Agencies, Jangaon order. Draft only.",
  "Which weekday do we deliver most in Hanamkonda?",
  "Hanamkonda lo ae weekday lo manam ekkuva deliveries chestham?",
];

describe("closest saved prompt", () => {
  it("returns an exact match regardless of case and spacing", () => {
    const m = closest("  which weekday do we deliver MOST in hanamkonda? ", P)!;
    expect(m.exact).toBe(true);
    expect(m.prompt).toBe(P[1]);
  });
  it("finds the nearest prompt for a paraphrase", () => {
    const m = closest("weekday deliveries in Hanamkonda", P)!;
    expect(m.exact).toBe(false);
    expect(P).toContain(m.prompt);
    expect(m.score).toBeGreaterThanOrEqual(0.3);
  });
  it("matches a truck-planning request to the planning prompt", () => {
    expect(closest("plan a truck for Lakshmi Agencies Jangaon", P)!.prompt).toBe(P[0]);
  });
  it("returns null when nothing is close", () => {
    expect(closest("hello there", P)).toBeNull();
    expect(closest("", P)).toBeNull();
  });
  it("works for Telugu script input without crashing", () => {
    expect(closest("రేపు జనగామ లక్ష్మి ఏజెన్సీస్ లోడ్ కి బండి పెట్టు", P)).toBeNull();
  });
});
