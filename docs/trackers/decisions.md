---
tags: [tracker, decisions]
---
# Decisions log

ADR-style: newest at the bottom. Never delete an entry; mark it superseded instead. Template: `templates/decision`.

| ID | Date | Decision | Status |
|---|---|---|---|
| D-001 | 2026-10-27 | Theme is **Build for Your World** only | superseded by D-018 |
| D-002 | 2026-10-27 | Rename "Self-Evolving" to **Self-Improving** | accepted |
| D-003 | 2026-10-27 | Voice-note input is P0, **gated on the Day-1 Telugu transcription test (T6)** | accepted (pending T6) |
| D-004 | 2026-10-27 | Muse plays 3 roles: agent, transcriber, diagnostician/proposer | accepted |
| D-005 | 2026-10-27 | No real user data and no testimonials; impact comes from cited stats and measured timing | accepted |
| D-006 | 2026-10-27 | Cut order: open weights → paraphrase probes → polish → tools 40→25 → arm A → voice | accepted |
| D-007 | 2026-10-27 | BigTool's expected win is tokens, cost and latency; accuracy is reported honestly | accepted |
| D-008 | 2026-10-27 | 48 tasks (32 dev / 16 held-out); held-out tasks run ×3 | accepted |
| D-009 | 2026-10-27 | Drop arm D (ablation) and non-Meta comparison | accepted |
| D-010 | 2026-10-27 | Docs are Markdown; `docs/` is the Obsidian vault | accepted |
| D-011 | 2026-10-27 | No Claude co-author or collaborator on pushes to `prashanth-ds-ml` | accepted |
| D-012 | 2026-10-27 | `Hackathon_info/` PDFs are never committed (they contain personal email and form pages) | accepted |
| D-013 | 2026-10-27 | Capacity is 8–10 hrs/day; Nov 4 IST is the buffer day | accepted |
| D-014 | 2026-10-27 | Runtime model: **`muse-spark-1.3` standard mode**, frozen for all evals. Not contributor mode | accepted |
| D-015 | 2026-10-27 | Commits use the personal email `prashanth01071995@gmail.com` (repo-local git config) | accepted |
| D-016 | 2026-10-27 | Python 3.12 with `uv`; OpenAI SDK pointed at `https://api.meta.ai/v1` | accepted |
| D-017 | 2026-10-27 | **Headline:** "A Meta Muse-powered, Telugu-first agent that gets measurably better at discovering and using business tools through verified experience, without retraining the model." | accepted |
| D-018 | 2026-10-27 | Theme: **Push the Frontier** (supersedes D-001) | accepted |
| D-019 | 2026-10-27 | Proof-case domain: **FMCG/kirana wholesale distributor** (AP, fictional data). Pharma, agri-input, dairy, spare parts and other languages are future adoption targets only | accepted |
| D-020 | 2026-10-27 | Retrieval recall@k (B → C) is a headline metric alongside task success | accepted |
| D-021 | 2026-10-27 | Repo and project name: **`meta-hackathon-telugu-agent`** (GitHub repo and Python project). Local folder stays `C:\Users\prash\projects\meta_hackathon`; it does not affect the remote, package or submission. Import package stays `order_agent` | accepted |

---

### D-001: Theme is Build for Your World only
- **Context:** PRD v1 hedged between "Push the Frontier" and "Build for Your World".
- **Decision:** Submit under Build for Your World.
- **Alternatives:** Push the Frontier, whose examples are robotics, energy, materials and physical systems; a weak fit.
- **Consequences:** One clear story. The self-improving harness becomes the technical *how*, not the theme.
- **Rubric impact:** Impact (fits the problem statement), Stage 1 pass.

> **D-001 superseded on 2026-10-27 by D-018.** The owner's headline makes the capability the product, which fits Push the Frontier.

### D-003: Voice gated on the T6 test
- **Context:** Voice adds a second Meta model and the video hook, but Telugu support in Muse Voice Transcribe is unverified.
- **Decision:** Run T6 on Day 1. Voice goes IN only if the transcripts can drive the golden path.
- **Consequences:** If it goes OUT, the ~3 hrs go to polishing the improvement loop.
- **Rubric impact:** Meta tooling, Demo.

### D-005: No real user data
- **Context:** No access to wholesalers; getting consent would take too much of 8 days.
- **Decision:** Fictional data; the developer records their own voice notes; public stats are cited and verified; a self-timed manual-vs-agent study is labeled as self-timed.
- **Consequences:** The Impact story rests on scale plus measured numbers. Never invent quotes.

### D-006: Cut order
- **Context:** Cutting tools first (as in v1) would make the BigTool comparison meaningless.
- **Decision:** See the table. Never cut the live quote path, traces, the verifier, at least one improvement decision, or video day.

### D-017 / D-018: Headline and theme
- **Context:** The owner set the headline around the agent's capability: getting better at discovering and using tools through verified experience, without retraining. The concepts behind it are langgraph-bigtool (tool retrieval at scale) and Harness² (improve the harness, not the model).
- **Decision:** Submit under Push the Frontier. The Telugu business is the proof case, not the product.
- **Consequences:**
  - BigTool retrieval and the improvement loop are the core.
  - Recall@k becomes a headline metric (D-020).
  - The headline needs a subline that names the human beneficiary, to cover Impact (30%).
  - "Measurably" requires a real, honestly reported held-out uplift (R-04).
- **Rubric impact:** Meta tooling, Tech, Impact (through the adoption path).

### D-019: Proof-case domain stays FMCG/kirana distributor
- **Context:** Pharma distribution was considered: richer tools and higher stakes, but some anti-project perception risk and a rebuild. The owner prioritised the best demo they can build solo.
- **Decision:** Keep the already-built FMCG/kirana distributor. List pharma, agri-input, dairy, spare parts and other languages as adoption targets on the final video slide and in the README.
- **Consequences:** No rebuild cost, and zero perception risk. The impact story is breadth across domains.

### D-014: Muse Spark 1.3, standard mode
- **Context:** Smoke tests passed on 1.3. Contributor mode is ~12× cheaper but lets Meta train on our prompts, and is limited to 150 RPM.
- **Decision:** Use `muse-spark-1.3` standard for everything that's measured. The estimated benchmark cost is under $10, so cost isn't a constraint.
- **Alternatives:** Contributor mode (cheaper, but adds a data-use question and a lower rate limit); 1.2 (recommended for audio input, but we transcribe separately).
- **Consequences:** One frozen model ID for the "same frozen model" claim (AT-09). Voice goes through Muse Voice Transcribe, not Spark audio input.
- **Rubric impact:** Tech (clean experiment), Meta tooling (latest model).
