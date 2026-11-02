import { readFileSync, readdirSync } from "node:fs";
import { describe, it, expect } from "vitest";
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";

const dir = "fixtures";
const schema = JSON.parse(readFileSync("../contracts/events.schema.json", "utf-8"));
const validate = addFormats(new Ajv2020({ allErrors: true })).compile(schema);

describe("event fixtures match contracts/events.schema.json", () => {
  for (const f of readdirSync(dir).filter((x) => x.endsWith(".jsonl"))) {
    it(f, () => {
      const rows = readFileSync(`${dir}/${f}`, "utf-8").split("\n").filter(Boolean).map((l) => JSON.parse(l));
      expect(rows.length).toBeGreaterThan(0);
      for (const r of rows) expect(validate(r), JSON.stringify(validate.errors)).toBe(true);
    });
  }
  it("rejects an unknown event type", () => {
    expect(validate({ run_id: "x", seq: 0, agent_id: "planner", agent_run_id: "x", caller: "person", depth: 0, ts: null, type: "nope", payload: {} })).toBe(false);
  });
});
