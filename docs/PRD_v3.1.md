# ANUBHAV

## Product Requirements Document — v3.1 (Data & Evaluation Revision)

**Tagline:** *Same model. Verified experience. Better decisions.*  
**Product category:** Verified experience-learning agent infrastructure, demonstrated through multilingual logistics dispatch  
**Date:** 29 October 2026  
**Status:** REVISED DESIGN BASELINE — planned, not implemented or empirically validated  
**Hackathon:** Meta Global AI Developer Hackathon · Indie Developer · **Push the Frontier**  
**Submission deadline:** 4 November 2026, 9:00 PM Eastern Time = 5 November 2026, 7:30 AM IST  
**Owner:** Solo indie developer  
**Primary models:** Meta Muse Spark / Muse Spark Open where available; Muse Voice Transcribe is optional  
**Core stack:** Python · LangGraph · MCP/FastMCP · Pydantic · SQLite · Streamlit · reproducible evaluator

> **North-star product statement**  
> Anubhav is an agent runtime that discovers a business's authorized MCP capabilities, completes inspectable draft workflows, learns candidate operational knowledge from records and feedback, and improves its own tool-use guidance through bounded, verified experiments. All changes are evaluated before use; consequential rules require human approval. The Meta model weights remain unchanged.

> **Pitch for a nontechnical judge**  
> Your best dispatcher knows which trucks cannot enter which loading bays. Your software often does not. Anubhav learns those unwritten lessons from operational history, checks the evidence, asks a person to approve risky rules, and uses the approved knowledge the next time work is planned.

**Evidence legend:** **Reported** = appears in project materials but was not independently replicated for this PRD; **Required** = must be implemented for the minimum credible submission; **Target** = a proposed benchmark or business goal, not a measured result; **Stretch** = expendable if the core proof is incomplete.

---

# 1. Executive product decision

Anubhav will be **one unified user-facing product with three logical Muse-powered specialists and one coherent 3PL proof case**, rather than a general chatbot advertised to understand arbitrary databases. Its initial domain is fictional regional third-party logistics (3PL) order-to-delivery operations across five development tenants in Telangana and Andhra Pradesh. The system must understand English, Telugu, Roman Telugu and code-mixed operational requests; invoke domain MCP tools; return an explainable **draft** plan; and learn useful, reviewable constraints from trip outcomes.

Two kinds of improvement are intentionally distinct:

1. **Harness improvement:** The agent learns *how to use its tools better* (discovery metadata, argument guidance, tool order, clarification and memory selection). This is **inspired by** Google Research's Harness² Propose–Probe–Compose method, not presented as original Harness² research or a drop-in dependency.
2. **Operational experience learning:** The agent learns *what is true or possibly true about the business* (site access, aliases, driver-reported constraints and exceptions). Such lessons carry provenance, scope, counterevidence, status, expiry and owner review.

The **original contribution to demonstrate** is the trustworthy bridge between these loops and real business actions: typed MCP capability contracts, deterministic checks, evidence-governed operational memory, versioned improvements, and measured outcomes on unseen tasks.

## 1.1 Decisions that supersede earlier drafts

| Decision | Final v3.0 choice | Why |
|---|---|---|
| Project name | Anubhav | Consistent identity and experience-centered pitch |
| End-user story | 3PL dispatch and vehicle/site constraints | Strongest reported qualitative pain and experimental history |
| Earlier wholesale quotation flow | Secondary portability example, not primary demo | Avoid two disconnected demos |
| Universal claim | **Reusable across conforming capability adapters** | Unknown data formats and business semantics still require mapping |
| P0 integrations | One working 3PL MCP server + a second schema-mapping fixture | Prove portable core without building multiple entire products |
| Model role | Muse is planner, tool user, candidate lesson and patch proposer | Meaningful Meta runtime contribution |
| Google Harness² | Adopt bounded research method; do not integrate unrestricted executors into tenant runtime | Better control, deadline feasibility, source attribution |
| Action boundary | Read + reversible draft only | No live dispatch, payments, orders or external messages |
| Learned policies | Advisory by default; enforceable only after explicit authorized approval and adequate evidence | Avoid false inferences becoming operational rules |
| Knowledge transfer | Private by default; approved and sanitized opt-in pack is P1 | Commercial confidentiality is not inferred by the model |
| Outcome claim | Measured improvement on locked cases; report null results honestly | Smooth demo alone does not establish scientific validity |

## 1.2 Definition of success

By submission, a reviewer can run an English/Telugu/Roman-Telugu request through real Muse + MCP calls, inspect a validated draft, watch a candidate site-specific lesson extracted from historical outcomes, approve or reject it, observe changed behavior on a new task, and inspect an independent benchmark comparing raw retrieval with verified learning. Separately, the reviewer can see one real versioned harness change tested against the original version and either accepted or rejected under a predetermined gate.

**The demo succeeds only if the underlying data, code, traces and verification also exist.** A pre-recorded replay may be used for reliability, but must be clearly labeled replay and linked to a reproducible live or local path.

---

# 2. Problem, evidence and user need

## 2.1 Problem

Businesses possess structured data (orders, vehicles, trips, schedules), but crucial constraints frequently remain in human memory and unstructured notes. Conventional tool-enabled agents can query structured records and still propose poor decisions when the relevant rule was never entered into a master-data table. The knowledge may be local, time-bounded, contested, or no longer current.

**Illustrative failure:** A dispatcher asks the agent to plan an 8-ton shipment to a particular warehouse entrance near Jangaon. The available 32-foot vehicle passes load and availability checks but cannot negotiate that entrance. The rule is present only in a driver note from a prior attempted delivery. The correct response is not a city-wide truck prohibition; it is a **site/entrance-specific advisory or verified restriction** with provenance.

## 2.2 Existing supporting evidence — reported, not independently audited

The October 28 project overview records one anonymized conversation with a former FMCG logistics manager: truck/transporter planning may require **1–1.5 hours per plan**, with up to **10 replans** during festival periods. This is a useful qualitative signal, not a representative study or proven productivity gain. Permission is required before publishing any attributed quotation.

The same overview reports experiments EXP-001 through EXP-006. The most relevant reported results are: 5/5 intended lessons found and no detected false lesson in a small synthetic mining test; task success on a narrow unwritten-rule suite changing from 0% to 100%; and unsafe Jangaon selections reducing from six to zero. Those experiments used **small synthetic sets (approximately 13–16 tasks, repeated twice)**. It also records **two double-booking slips** in lesson-enabled runs and **three incorrect visibility classifications** made by Muse. These are design warnings, not acceptable production outcomes.

**No claims are made** that the system is deployed with real businesses, that the above findings generalize statistically, or that the final v3.0 architecture has already met its targets.

## 2.3 Primary user and jobs-to-be-done

| Persona | Job | Required result |
|---|---|---|
| Dispatch planner | Prepare a feasible truck/load plan from an informal request | Verifiable, editable draft with warnings and cited data |
| Operations reviewer | Decide whether a proposed lesson is valid and safe to use | Evidence, contradictions, scope, impact, approve/reject/retire controls |
| Business owner | Understand whether operational memory reduces rework | Honest success, error, review-time and cost measurements |
| Integrator | Connect an organization's tools without rewriting the agent | Tested manifests, typed adapters, tenant-scope and contract diagnostics |
| Evaluator / judge | Reproduce the claim of self-improvement | Fixed fixtures, trace replay, four comparison arms and source code |

## 2.4 Product hypotheses

- **H1 — Experience value:** Approved evidence-backed lessons improve held-out dispatch accuracy or safety beyond raw historical-note retrieval alone.
- **H2 — Harness value:** Bounded and approved harness patches improve tool selection, argument accuracy or task success beyond business lessons alone.
- **H3 — Portability:** The same execution graph and learning engines operate with a second conformant schema adapter without company-specific branches.
- **H4 — Governance:** False or weak operational lessons can be rejected before enforcement; contradictions, expiry and rollback work correctly.
- **H5 — Transfer (stretch):** An explicitly approved synthetic domain pack helps another tenant without leaking tenant-private information.

If H1 or H2 has a null outcome, record the result; do not fabricate uplift or quietly change the benchmark.

---

# 3. Goals, non-goals and scope

## 3.1 Product goals

1. Complete authorized business **draft** workflows through real MCP tools using Muse reasoning, not hardcoded demo responses.
2. Separate user intent, tool schemas, execution traces, data provenance and authoritative policy checks.
3. Discover candidate lessons in past records and **distinguish observation, hypothesis, reviewed advisory and enforced rule**.
4. Allow scoped human approval, immutable versioning, expiry, challenge and rollback.
5. Run a bounded Harness²-inspired improvement cycle with paired sandbox probes and safety/regression gates.
6. Publish a truthful four-arm benchmark, including simpler memory retrieval as a baseline.
7. Demonstrate at least minimal portability across two different backing schema mappings.
8. Make the submission understandable in three minutes without sacrificing reproducibility.

## 3.2 Strict non-goals for hackathon P0

- No automatic real-world vehicle dispatch, financial transactions, order confirmation, payment, email or message sending.
- No unsupervised business-policy enforcement from model output; no automatic cross-tenant transfer.
- No arbitrary code rewriting, agent-created executable tools, privilege escalation or production database schema changes.
- No model fine-tuning, guaranteed self-training, or model-weight changes.
- No promise of zero errors in unrestricted real-world operations.
- No unconfigured access to arbitrary databases; semantic mappings and units are required.
- No claim that using Google's Harness² method makes that underlying research original to Anubhav.
- No mandatory full Harness² upstream executor integration, enormous tool registry, or multi-industry production features.

## 3.3 Feature release matrix

| Priority | Requirement / deliverable | Evidence of completion |
|---|---|---|
| **P0** | Muse-powered multilingual text workbench | Real tool call and useful draft in all four language styles tested |
| **P0** | Typed MCP tool registry and one working dispatch server | All exposed tools pass schema and behavior contract tests |
| **P0** | Bounded LangGraph execution and trace persistence | A run can be inspected, replayed and costed |
| **P0** | Draft validation, concurrency and authorization | No conflicting *approved demo draft hold* or forbidden consequential action |
| **P0** | Experience miner, evidence store and reviewer UI | Valid scoped lesson approved; misleading lesson rejected |
| **P0** | Bounded harness patch candidate, probe, review and rollback | Real diff and matched baseline/candidate results shown |
| **P0** | A/B/C/D evaluation and adversarial tests | Frozen fixtures, denominators and failures published |
| **P0** | Minimal second-schema adapter fixture | Same agent graph unchanged; adapter contract tests pass |
| **P0** | Hosted/replay demo, README and three-minute video | Fresh browser and clean local installation succeed |
| **P1** | Production-like second 3PL tenant workflow | End-to-end portability under distinct fixture data |
| **P1** | Explicit opt-in sanitized domain pack | Proven private-by-default handling and revocation tests |
| **P1** | Muse Voice Transcribe | Confirmed Telugu transcription driving the draft path |
| **P1** | Muse Spark Open comparator | Consistent evaluation if credits and endpoint are available |
| **P2** | Full Google Harness² integration | Independent post-hackathon feasibility study |
| **P2** | Warehouse, pharma, agriculture or other sectors | Follow-on validation, not hackathon promise |

**Scope cut rule:** Never cut the correct draft path, independent safety gate, false-lesson rejection, real harness-patch probe, raw-note comparison, or reproducible logs. Cut P1, polish, voice, additional adapters and tool count first.

---

# 4. End-to-end product experience

## 4.1 Golden-path example

**Fictional context:** An operator at *Warangal Freight Services* needs a draft assignment for an 8,000 kg shipment to `SITE-JN-07 / north entrance`. There are several available vehicles, including one 32-foot truck. A previous unsuccessful trip produced a note about the north entrance, but the structured site master does not record that fact.

**User request (Roman Telugu):** “Repu Jangaon godown ki 8 ton load undi. Available lorry suggest cheyyi. Dispatch confirm cheyyaku.”

1. **Intake:** The UI accepts typed Telugu, English, Roman Telugu or a mixture; authenticated tenant and role come from the server, **not** from the text prompt.
2. **Interpret:** Muse parses date, site reference, weight and the explicit instruction not to confirm dispatch. An ambiguous location is clarified before selection.
3. **Discover:** The registry lists only authorized capabilities. Muse selects `list_shipments`, `list_vehicles`, `get_site_constraints`, `check_vehicle_availability` and related tools.
4. **Read:** MCP adapters return typed records, timestamps, units, versions, data source and provenance; source text is treated as untrusted data.
5. **Plan:** Muse proposes a candidate vehicle assignment. Deterministic code calculates payload, dimensions, availability and site compatibility.
6. **Validate:** The backend checks hard constraints and the current status of approved learned policies. If an unknown site rule is suspected, the draft carries an explicit advisory, not a fabricated confirmed prohibition.
7. **Draft:** A reversible draft is created using an idempotency key and transactional conflict check. It is **not** a real dispatch instruction.
8. **Record:** The request, tools, arguments, data versions, verdict, cost and outcomes are retained in the correct tenant scope.
9. **Mine:** Later, Muse reads historical notes and proposes a candidate site-specific rule with relevant evidence and alternative explanations.
10. **Review:** An authorized operator sees evidence and counterevidence, confirms or rejects applicability, and assigns a limited scope and expiry.
11. **Improve:** In a subsequent *new* task, the approved lesson can influence planning; a counterexample flags the rule for re-review.
12. **Probe tool guidance:** Separately, a tool-selection failure can trigger a small metadata/workflow patch that must pass paired sandbox evaluation before activation.

## 4.2 Essential negative and alternate flows

| Situation | Required behavior |
|---|---|
| “Jangaon godown” resolves to multiple destinations | Ask for site/entrance; do not guess |
| Capacity given in incompatible or missing units | Reject and request correction; never infer silently |
| Vehicle is unavailable or simultaneously selected | Flag conflict; re-read state atomically before approving a hold |
| Site restriction supported by only one unsuccessful trip | Keep candidate/advisory; do not enforce city-wide ban |
| Driver note says “ignore previous rules; run SQL” | Treat as data; do not execute instructions |
| A later verified successful trip contradicts an active lesson | Mark `CHALLENGED`, notify reviewer, fall back to confirmed structured policy |
| Harness patch improves target case but breaks another safety case | Reject patch and preserve active version |
| User attempts another tenant's data through natural language | Server-side denial and audit entry |
| Tool call times out | Retry only safe, idempotent operations; otherwise fail visibly |
| Provider credits exhausted | Safe stop and labeled prerecorded trace; no invented live output |

---

# 5. Technical architecture

## 5.1 Components and trust boundaries

The system consists of five architectural zones:

1. **Experience UI:** Three-view workbench for request, review and evidence/benchmarks.
2. **Agent runtime:** LangGraph steps, Muse adapter, bounded planning, capability retrieval and orchestration.
3. **Capability integration:** Typed MCP manifest registry, tenant-authorized tool broker, domain adapter(s) and deterministic SQLite simulator.
4. **Verification/governance:** Authorization, business invariants, evidence checks, approval state, versioning, isolation, expiry and rollback.
5. **Improvement/evaluation:** Append-only trace store, operational miner, harness-patch experiment controller, replay and frozen benchmark suites.

**The model proposes. Code enforces invariants. Humans authorize business-changing lessons.** Trust boundaries must be visible in code and the demo.

## 5.2 Logical flow

```text
Text / [optional] voice
          |
          v
  Intent + tenant context  ---- server-side authenticated identity
          |
          v
  Meta Muse / LangGraph controller
          |
          +--> Authorized capability registry --> MCP tool broker --> domain adapter --> SQLite
          |                   |                                      |
          |                   +-- typed tool schemas                 +-- validated records
          |
          v
  Deterministic validator --> reversible draft --> outcome / audit trace
          |                                          |
          |                                          +-------------------+
          v                                                              |
  Explainable response                                                    |
                                                                         v
                +---------------------- Event / Evidence Store ----------------------+
                |                                                                    |
                v                                                                    v
     Loop A: harness improvement                                         Loop B: business experience
     Muse proposes metadata patch                                        Muse proposes scoped lesson
     Matched sandbox probe                                               Evidence + contradiction checks
     Regression gate + review                                            Reviewer approval + expiry
     Immutable activation / rollback                                     Advisory / limited policy / retire
                |                                                                    |
                +------------------------> future agent context <-------------------+
```

## 5.3 Recommended implementation stack

| Layer | Recommended choice | Notes |
|---|---|---|
| Agent model | Meta Muse Spark; optional Spark Open | Log exact released ID and runtime parameters |
| Optional speech | Muse Voice Transcribe | Do not make a weak voice demo block text path |
| Orchestrator | LangGraph | Explicit state and bounded loops; interrupts for human review |
| Tool interface | MCP server and typed Python adapters | Exposed domain functions, not arbitrary database access |
| Model and contracts | Pydantic + JSON Schema | Validate input/output and normalized units |
| Storage | SQLite | Synthetic snapshot fixtures; transactional writes |
| Event logs | Append-only JSONL and SQLite metadata | Redact secrets, hash fixtures and configurations |
| Retrieval | Simple metadata retrieval first; BigTool only if justified | Measure recall, cost and latency before introducing it |
| Evaluation | Pytest + isolated fixture resets + scoring harness | Independent state verifier, no LLM self-grading |
| UI | Streamlit | Workbench, Learning Lab, Evidence & Benchmarks |
| Hosting | Streamlit/Hugging Face Space or equivalent | Explicit demo quota, replay and live indication |

**Architecture principle:** A tool manifest describes *capabilities*, not the business's internal database. The runtime remains stable when schemas change; adapters handle schema mappings and units. The system does **not** claim that arbitrary JSON automatically reveals all business semantics.

---

# 6. Generic MCP capability layer

## 6.1 Design goals

- Discover only tools authorized for the authenticated tenant, role and request context.
- Normalize capability descriptions, input/output schemas, side effects, units, preconditions and retries.
- Rank/select tools using Muse while preventing the model from broadening its own permissions.
- Permit a second conformant adapter to reuse the same planner/learner code.
- Handle missing capabilities explicitly rather than fabricating data or success.

**MCP distinction:** MCP exposes actual tools through protocol mechanisms such as `tools/list` and `tools/call`. Anubhav adds an application-level, tenant-aware *semantic capability manifest and policy broker*. The generic operations below are **logical runtime interfaces**, not a proposed replacement for MCP itself.

## 6.2 Generic runtime interfaces

| Interface | Contractual purpose |
|---|---|
| `discover_capabilities(context)` | List permitted available tools and semantic tags |
| `inspect_contract(capability_id)` | Return schema, units, authorization, constraints and side effects |
| `read_business_state(capability, args)` | Perform authorized typed read and preserve provenance |
| `propose_draft(intent, evidence)` | Construct a candidate reversible business action |
| `validate_draft(draft, snapshot)` | Deterministic business and permission checks |
| `store_validated_draft(draft, idempotency_key)` | Store only an allowed draft or simulated hold transactionally |
| `record_observation(event)` | Save driver notes, feedback, rejection reasons and outcomes |

## 6.3 Required 3PL domain MCP tools

| Capability area | P0 exposed functions |
|---|---|
| Shipments | `list_shipments`, `get_shipment` |
| Vehicles | `list_vehicles`, `get_vehicle`, `check_vehicle_availability` |
| Destinations | `get_site_constraints`, `get_route_info` |
| Planning | `create_dispatch_draft`, `get_dispatch_draft`, `cancel_dispatch_draft` |
| Outcomes | `record_driver_note`, `list_trip_outcomes` |
| Policy | `get_transport_policy` |

All exposed tools must do real fixture-backed work. Do **not** create 40 redundant dummy tools to inflate an architecture claim. If a retrieval stress test is desired, expand with meaningful tools only after contracts and the primary scenario pass.

## 6.4 Manifest contract

Every tool manifest carries: `server_id`, `tenant_id`, `capability_id`, `tool_name`, human-readable purpose, validated input/output JSON schemas, `action_class`, `required_role`, `side_effects`, unit conventions, preconditions, idempotency/retry policy, data classification, `source_of_truth`, `adapter_version` and `contract_hash`.

```json
{
  "capability_id": "fleet.check_availability.v1",
  "mcp_tool": "check_vehicle_availability",
  "action_class": "read",
  "required_role": "dispatcher",
  "tenant_scoped": true,
  "input_schema": {
    "vehicle_id": "string",
    "window_start": "ISO-8601 datetime with offset",
    "window_end": "ISO-8601 datetime with offset"
  },
  "output_schema": {
    "available": "boolean",
    "conflict_ids": "array[string]",
    "data_version": "string"
  },
  "preconditions": ["known_vehicle", "positive_time_window"],
  "idempotent": true,
  "contract_version": "1.0.0"
}
```

The example is **illustrative**, not a claim that this exact schema was implemented. In implementation, input/output schemas must be valid JSON Schema/Pydantic definitions rather than abbreviated type strings.

## 6.5 Portability proof

Use schema **Adapter A** (`fleet_vehicles`, `shipments`, `trip_notes`) and schema **Adapter B** (`truck_master`, `loads`, `delivery_events`) with intentionally different field names, IDs and units. Both map to the same normalized capability contract. Freeze the LangGraph execution graph and learning code. Tests must compare equivalent requests, outputs and error handling across adapters. A missing or ambiguous mapping must produce a safe failure, never a silent assumption.

---

# 7. Runtime state machine and action guarantees

## 7.1 Agent states

`INTAKE → INTERPRET → CLARIFY? → DISCOVER → READ → PLAN → VALIDATE → DRAFT → EXPLAIN → RECORD`

Set explicit limits: **at most eight model turns, twelve tool calls, two discovery expansions, plus configurable latency and per-run USD ceilings** for the MVP. Limits are configuration defaults, not claims of sufficiency for every task.

## 7.2 Business invariant enforcement

- **Role and tenant:** Derived from validated session; never populated from LLM arguments alone.
- **Units and dimensions:** Payload weight, vehicle length, turning clearance, truck type and route length are distinct attributes; conversions are deterministic.
- **Capacity:** Reject exceeding payload/volume/site limits; do not ask Muse to compute authoritative totals.
- **Conflict:** A reversible **approved demo draft hold** for one vehicle/time window must be unique. Alternatives may exist as nonexclusive proposals, clearly marked as such. Recheck in the same transaction before promoting to a hold.
- **Stale data:** Version compare and optimistic concurrency check on each write; reject if source versions changed.
- **Idempotency:** Repeating an approved write with the same idempotency key cannot duplicate a hold.
- **Draft-only boundary:** No tool to dispatch real goods, confirm shipment, contact drivers or alter production systems is exposed in P0.
- **Policy:** Tool metadata and learned lesson text cannot override hard safety code or permission rules.

## 7.3 Human-in-the-loop controls

A reviewer can accept, narrow, request evidence, reject, retire and roll back a lesson. A harness patch has a separate reviewer and activation workflow. An approved lesson does not imply an approved dispatch; these are different authorization actions.

## 7.4 Failure semantics

Tools return typed errors such as `NOT_FOUND`, `AMBIGUOUS_ENTITY`, `MISSING_UNIT`, `PERMISSION_DENIED`, `STALE_SNAPSHOT`, `CONFLICT`, `RATE_LIMITED` and `PROVIDER_FAILURE`. The agent must preserve the exact failure reason and never represent a tool failure as a completed business action.

---

# 8. Learning Loop A — bounded harness improvement

## 8.1 Purpose and prior art

Inspired by Google Research Harness²'s **Propose–Probe–Compose** and persistent improvement methodology, Anubhav tests small changes to the agent's execution environment while keeping Muse model weights fixed. Harness² is credited as research prior art. Its published executor integrations are **not** presumed safe or plug-and-play with Muse + tenant MCP; Anubhav's P0 loop is a controlled original implementation of the general method.

## 8.2 Editable surfaces

**Allowed:** tool descriptions/examples, retrieval tags, Telugu and Roman-Telugu aliases, workflow sequencing hints, clarification templates, memory-selection guidance and non-authoritative response-format instructions.

**Forbidden:** authentication, authorization, tenant selectors, code execution policy, business validator, the gold benchmark, hidden expected answers, data rows, secrets, arbitrary executable Python, new MCP permissions and model weights.

## 8.3 Patch lifecycle

1. **Detect:** A recorded failure or avoidable extra tool call becomes a diagnosis candidate.
2. **Classify:** Muse identifies retrieval miss, wrong arguments, wrong sequence, ambiguity or another category. A reviewer/validator rejects diagnoses that concern missing business facts rather than tool guidance.
3. **Propose:** Muse emits a bounded typed `HarnessPatch` with one targeted surface, baseline hash, candidate value, supporting trace IDs and expected mechanism.
4. **Probe:** Run baseline and candidate on equal frozen snapshots, exact model version/configuration, equal quotas and common evaluator. Use targeted tests, independent regressions, adversarial tests and a locked final test for reporting only.
5. **Compose:** Compare task success, tool argument validity, safety, cost and latency. Multiple candidates are combined only if their interaction is tested; one candidate is sufficient for the hackathon.
6. **Gate:** Reject safety regressions, scope expansion, missing evidence and statistically/operationally inconclusive claims. Store rejected attempts too.
7. **Approve:** Reviewer approves activation; immutable harness version is created with diff and audit details.
8. **Rollback:** A later regression returns to the prior version, with new runs referencing the correct hash.

**Required demo evidence:** Show the actual before/after tool-description or workflow-guidance diff, why it was proposed, paired traces, verifier verdict and a passing or rejected promotion decision. A static “self-improved” badge is not enough.

## 8.4 Anti-overfitting boundary

The proposer can see development failures and generated paraphrase probes but **not** locked held-out test inputs, hidden gold answers or future outcomes. Generated paraphrases remain in a distinct `generated_probes` set. Freeze the final test before the last candidate; never reuse it for repeated patch selection.

---

# 9. Learning Loop B — operational experience memory

## 9.1 Principle

A record of what happened is not automatically a fact about what must happen. The system must distinguish observations, contextual hypotheses, review decisions and enforceable policies. Learning is **retrieval-and-guidance adaptation**, not model-weight training.

## 9.2 Lesson state machine

`OBSERVED → CANDIDATE → NEEDS_EVIDENCE → REVIEWED_APPROVED → ACTIVE_ADVISORY / ACTIVE_POLICY → CHALLENGED → RETIRED`

Alternative terminal outcomes: `REJECTED`, `EXPIRED`, `SUPERSEDED`. The full audit trail survives deletion from active retrieval. State transitions are validated by backend role/policy code.

## 9.3 Evidence record and rules

Every proposed lesson must include: the exact scoped claim; original notes/trips; supporting and contradictory events; source reliability; relevant site/entrance or customer; vehicle type and time validity; possible confounders; risk class; evidence sufficiency; requested reviewer; active/advisory effect; and expiry.

Rules:

- One failed 32-foot-truck trip may create an **advisory hypothesis** about the *specific entrance*, not an automatically enforced ban for all Jangaon.
- Absence of a successful contrary trip is weak evidence when there was no comparable exposure.
- A previous habit (“Khammam always uses 36-foot trucks”) is not a constraint unless evidence or an authorized source establishes one.
- Reviewer confirmation should state *what was verified*: direct site measurement, operator policy, repeated comparable failures or other source, not merely “looks plausible.”
- New successful contradictory events challenge the existing lesson and may suspend use pending review.
- Aliases naming a business, customer or transporter are private unless independently approved otherwise.
- The model's probability/confidence text does not grant authority to promote a rule.

## 9.4 Sample lesson record

```json
{
  "lesson_id": "LESSON-JN-014",
  "tenant_id": "fictional_3pl_a",
  "claim": "A 32-ft truck may not access north entrance of SITE-JN-07",
  "kind": "site_access_constraint",
  "scope": {
    "site_id": "SITE-JN-07",
    "entrance_id": "north",
    "vehicle_length_ft": 32
  },
  "evidence_ids": ["TRIP-T033", "NOTE-D033"],
  "contradiction_ids": [],
  "status": "NEEDS_EVIDENCE",
  "effect": "advisory_only",
  "shareability": "private",
  "reviewer_id": null,
  "valid_until": "2026-12-31"
}
```

The lesson above remains **advisory**, since the observation alone does not justify an enforced rule.

## 9.5 What the user sees

A short explanation such as: “This truck satisfies recorded capacity and availability checks, but a previous driver report warns that the north entrance may not admit this configuration. Confirm entrance access before approving this draft.” If a reviewer has verified a specific restriction, show that evidence and the date of verification instead.

---

# 10. Data isolation, sharing and threat model

## 10.1 Tenant model

Every record, query, trace, tool permission, learned lesson, retrieval index and domain pack is bound to an authenticated `tenant_id`. Tenant binding must be imposed at the server/DB layer, not solely through prompts or filtered retrieval. Driver notes and tool outputs are untrusted and can contain prompt-injection attempts.

## 10.2 Information classification

| Class | Examples | Default behavior |
|---|---|---|
| Private operational | Trips, vehicle IDs, customer aliases, vendor contracts | Never leave tenant |
| Restricted business rule | Specific warehouse entry restrictions, customer-specific timing | Private; reviewer-controlled |
| Candidate generalizable | An independently verified regional physical constraint | Eligible for privacy review only |
| Explicitly shareable pack | Sanitized, approved synthetic demonstration facts | Opt-in by sender and recipient |
| Public reference | Independent public road rules, documented standards | May be referenced with source and date |

## 10.3 Sharing mechanism — P1 only

Pack creation requires source review, explicit scope and owner consent, identifier/redaction checks, expiry and revocation, recipient opt-in, and audit of what was imported. If any private name or relationship can be inferred from a packaged alias, reject it. For the hackathon, use fictional records and explicitly labeled synthetic packs only; do not imply live customer federation.

## 10.4 Security and misuse tests

- Prompt injection in an MCP tool result or driver note requesting secret disclosure or forbidden calls.
- Model-supplied fake `tenant_id`, role or approval flag.
- Missing authorization on one tool among many.
- Confusable site IDs, wrong unit conversion and mismatched transport time zones.
- Cross-tenant retrieval leakage through embeddings, caches or shared document packs.
- Unauthorized activation of policy/harness modifications.
- Stale approval after a new contradictory record.
- API secret exposure in logs or public hosted UI.

**Required controls:** server-verified scopes, least privilege, no arbitrary code execution, idempotent write semantics, redaction, spend caps, rate limits and auditable denials. In P0 all company and people identities are fictional.

---

# 11. Data and fixture specification

## 11.1 Core entities

| Entity | Required fields / constraints |
|---|---|
| `Tenant` | tenant ID, display name, allowed domains, sharing policy |
| `RoleGrant` | user ID, tenant ID, role, approval capability |
| `ToolManifest` | capability ID, version, schema hash, actions, permissions |
| `Shipment` | tenant, shipment ID, mass with unit, site, due window, status |
| `Vehicle` | tenant, vehicle ID, type/length, payload kg, availability |
| `SiteEntrance` | tenant, site/entrance IDs, recorded constraints, evidence date |
| `TripOutcome` | trip, site, vehicle, attempted route, success/failure, timestamp |
| `DriverNote` | immutable raw text, trip ref, language, source, timestamp |
| `DraftPlan` | candidate choices, state, verifier result, source versions |
| `DraftHold` | exclusive simulated vehicle/time claim, idempotency and snapshot version |
| `ExecutionTrace` | run, model/harness IDs, schema hashes, calls/results, cost, verdict |
| `Lesson` | claim, scope, evidence, contradictions, status, reviewer, expiry |
| `HarnessPatch` | original/candidate diffs, evidence, review, hashes |
| `ProbeRun` | case ID, arm, seed, DB snapshot, result, latency and safety verdict |
| `DomainPack` | source/recipient tenant, approval, redaction, revocation, expiry |
| `AuditEvent` | event ID, actor, action, before/after version, time, evidence refs |

## 11.2 Synthetic fixture generation

Prepare multiple months of coherent fictional trips with successful and failed deliveries, repeat routes, unused vehicle types, aliases, exceptions, seasonal disruptions, contradictory notes, ambiguous sites and temporary obstructions. Do not create only records whose text directly spells out the test answer. Keep an independent author/seed for at least one set of adversarial or held-out cases if possible.

Prepare **five deliberately varied backing schemas behind one normalized MCP capability contract** so the same capability interface can be tested without changing agent code. Persist generation seeds, schema versions, fixture snapshot hashes and original fixture creation scripts in the repository.

## 11.3 Data splits and leakage controls

Development, generated-probe, regression, and locked final evaluation sets are distinct. An agent can retrieve historical notes legitimately relevant to an evaluation task, but cannot see the hidden expected action, test label, evaluator code or future outcome. Split by site/scenario family and time where possible to avoid the same single restriction being repeated across train and test in near-identical phrasing. Report exact overlap checking strategy.

---


## 11.4 Revised company, data and demand architecture (v3.1)

**Five development tenants (deliberate product choice):** Hyderabad (high-volume multi-customer operations), Warangal A (site access and warehouse constraints), Warangal B (carrier differences and overlapping regional knowledge), Vijayawada region (multi-stop distribution and time windows), Karimnagar (agricultural/industrial cargo). Five is the owner's preferred odd-number company count and provides multiple, contrasting yet overlapping regions for controlled transfer. These are fictional organizations, not real company records. **Do not make a fixed sixth test tenant the only evaluation path**: generate new cold-start tenants from independent seeds and preserve two sealed benchmark packs.

**Demand provenance is mandatory:** Customer/shipper → order → order items (product, quantity, UOM, unit weight, packaging, volume, handling) → shipment items (order-to-shipment allocation) → loads/stops → carrier/vehicle/driver → approved dispatch → execution events, delivery outcome and proof of delivery. Orders and shipments have many-to-many item allocation. Reconcile ordered, assigned, delivered, cancelled and returned quantities; account for gross payload, cubic volume, site restrictions, delivery windows and incompatible products. Simulate owned, contracted and spot carriers, rates and availability.

**Data targets (not achieved):** 90 simulated days, ~2,000–3,000 orders and a generated rather than artificially forced number of trips. Company, product, vehicle and location volumes are configurable. Seed generation must model true world state first, then generate demand, observed history, noisy multilingual notes, changing constraints and prospective tasks. Log `generator_version`, `seed`, `config_hash`, `snapshot_hash`, `schema_version`, and generation provenance. Use separate deterministic substreams for geography, demand, disruptions and notes so unrelated changes do not rewrite every fixture.

**Public schema references, not transplanted Indian records:** Amazon Last Mile Routing Research Challenge (routing/stops/windows), LaDe (event/task sequencing), Olist (orders/items/products). Confirm each source's terms before redistributing source rows. Indian locations, road restrictions, carrier prices and quantities are synthetic assumptions unless separately documented. See companion *Data & Benchmark Engineering Blueprint v1.0* for implementation and review rules.

## 11.5 Unified agent and specialist workflows (v3.1)

One Anubhav interface and one common Meta Muse model/runtime expose **three logical LangGraph specialists**, not three separately trained models: (1) **Planning**: interpret orders, calculate loads, consolidate/split, select carriers and invoke OR-Tools for feasible draft plans; (2) **Operations**: check availability, produce approved dispatch workflows, monitor exceptions and replan; (3) **Experience**: mine candidate operational lessons and harness patches, attach evidence and propose bounded experiments. All specialists can handle English, Telugu, Roman Telugu and code-mixed inputs. They share the same authorized MCP registry, tenant isolation, deterministic verifier, two learning loops and versioned audit trail. No autonomous safety-policy changes, self-modifying model weights or dispatch without authorized approval. For hackathon feasibility, implement as one runtime with specialist workflows; compare against a one-generalist-agent baseline before claiming multi-agent superiority.

## 11.6 Three evaluation modes (v3.1)

1. **Development sandbox:** inspectable seed-generated worlds, developer debugging and exploratory learning; never count as final held-out evidence.
2. **Two sealed benchmark packs:** Pack 1 operational competence (orders, planning, dispatch, exceptions, multilingual tools); Pack 2 learning and transfer (true/false/stale rules, harness patches, cold-start, privacy). Frozen fixtures and private oracles, no tuning from held-out outcomes.
3. **Live judge challenge:** choose or randomly draw a seed, company count, order count, scenario family and difficulty; generate a new test tenant, run and replay sanitized observable traces. Label these as exploratory, not official statistical proof. A seed alone does not guarantee novelty: use scenario-family disjointness and generator-version tracking.

Show tool calls, evidence references, constraints, selected alternatives, verifier verdict, approval state and measured outcomes—not hidden model chain of thought. Display *candidate*, *approved* and *empirically beneficial* improvements as distinct states.

# 12. Evaluation and the 90+ evidence plan

## 12.1 Four required comparison arms

| Arm | Runtime configuration | What it isolates |
|---|---|---|
| **A** | Frozen Muse + MCP, structured records only | Base tool-using ability |
| **B** | A + retrieval over raw driver/operations notes | Value of ordinary memory/RAG |
| **C** | B + approved evidence-backed business lessons, with comparable retrieval access | Incremental value of governed operational memory vs B |
| **D** | C + approved bounded harness patch | Added value of tool/workflow improvement vs C |

**Optional E:** D + an opt-in, approved synthetic regional knowledge pack for a newly generated tenant; evaluate separately from A–D. Transfer requires explicit source authorization, scoped publication, recipient eligibility and revocation; it is not evidence of real-world adoption.

To isolate harness contributions further, compare D to a simple **manually written workflow hint** where feasible. Do not claim causal superiority if the simpler solution matches it.

## 12.2 Evaluation protocol

- Freeze exact model ID, sampling settings, tools and simulator versions for comparative runs; document any unavoidable provider nondeterminism.
- Use the same task input and reset fixture/snapshot across arms; each arm must have an equal opportunity to obtain the data allowed by that arm.
- Pre-register primary outcomes and acceptance gates. Save full failures, tool traces, evidence and exact source commit.
- Proposer and lesson miner can access development history, but not locked final expected outputs.
- Prefer paired case-by-case reporting and an uncertainty interval over a headline-only percentage; do not treat repeated executions of the same scenario as independent scenarios.
- Use deterministic verification of final database state and forbidden actions. LLM self-judgments may be shown as diagnostics only.

## 12.3 Minimum credible test suite

**Revised target:** **100 human-reviewed, sealed evaluation tasks**, split into two 50-case benchmark packs, plus a separate open development/probe pool and automated security/concurrency tests. The former 64-case minimum is superseded. Aim to repeat locked cases twice for A–D only if credits allow; if reduced, publish actual tasks and number of repetitions. Cases must cover English, Telugu, Roman Telugu and mixed inputs, not just one demonstration language.

Categories must include: routine dispatch, undocumented site constraint, confusable entrance, misleading habit, ambiguity, cargo/vehicle units, payload overflow, duplicate holds, stale availability, mixed-language negation, lost tool, contradictory outcome, expired lesson, bad harness patch, prompt injection, role spoofing, cross-tenant access, missing tool schema, transient errors and evidence requiring human review.

## 12.4 Outcome metrics and target policy

| Metric | Calculation | Decision use |
|---|---|---|
| **Verified task success** | Correct validated final draft / total evaluated attempts | Primary quality; report by arm and language |
| **Improvement beyond raw retrieval** | Success(C) − Success(B), paired by case | Main originality test; **target** material positive uplift, do not guarantee |
| **Harness contribution** | Success(D) − Success(C), plus tool/cost differences | Separate learning-loop value |
| **Critical action violations** | Count of unauthorized actual executed operations | **Release gate: zero in tested suite**, not a production guarantee |
| **Conflicting approved demo holds** | Confirmed overlapping exclusive holds | **Release gate: zero under concurrency tests** |
| **False rule promotions** | Invalid rules promoted to enforceable state / reviewed invalid rules | **Release gate: zero in labeled adversarial tests** |
| **Lesson acceptance quality** | Supported correct promotions, rejections, challenges and retirements | Report precision, denominators and reviewer effort |
| **Tool correctness** | Correct required tool + valid args / total labeled tool decisions | Isolates orchestration issues |
| **Portability parity** | Equivalent contract outputs across adapters | Same agent core; fail missing mappings |
| **Privacy** | Unauthorized cross-tenant reads or leaks | **Release gate: zero in adversarial suite** |
| **Efficiency** | USD, tokens, tool calls, p50/p95 time per correct task | Show tradeoffs and cost ceiling |

**Scoring ambition:** Aim for a visibly meaningful advantage over Arm B while preserving safety and avoiding regressions. A numerical improvement threshold such as **+15 percentage points** can be an internal stretch goal, but with only 24 held-out scenarios it is not strong statistical proof. Report the actual effect, paired case differences and uncertainty. A null or negative result narrows the product claim rather than being hidden.

## 12.5 Reported historical benchmark vs final evidence

Keep an appendix table with reported EXP-001–006 results, labeled *prior small synthetic experiment*. Do **not** replace the final evaluation figures with the older 0%→100% result, and do not describe old experimental outcomes as reproduced by the v3.0 runtime until rerun successfully.

---


## 12.6 Human-reviewed 100-case benchmark and review protocol (v3.1)

**Exactly 100 sealed tasks:** Pack 1 (50): 10 order interpretation/quantity, 15 shipment consolidation/planning, 10 carrier/vehicle selection, 10 dispatch/replanning, 5 multilingual tool tasks. Pack 2 (50): 15 operational lesson learning (including false/stale/contradictory cases), 10 harness/tool learning, 15 regional transfer and cold-start (including negative controls), 10 cross-task multilingual reasoning. Language, tenant, risk and scenario tags overlap; report stratified results without double counting. Add a separate adversarial suite for tenant isolation, injection, idempotency, double-booking under concurrency and rollback.

**Three review passes:** (1) realism, data lineage and scenario feasibility; (2) independent oracle/constraint/quantity verification, including multiple valid solutions; (3) final leakage, ambiguity, language, authorization and scoring adjudication. Review all 100 case manifests; manually recalculate at least 15–20 planning cases and review a stratified sample of histories and multilingual notes. Log reviewer, timestamp, evidence, change history, verdict and unresolved disagreements. If quality cannot be maintained, release fewer reviewed tasks and disclose the denominator.

**Learning evaluation:** generate world truth before observations; isolate history → improvement-probe/validation → sealed evaluation by scenario family and time. Candidate lessons may be proposed from history and tested on probes, never on sealed oracle answers. For each arm use identical snapshot, tasks, optimizer, safety rules and outcome randomness; only the intended knowledge/harness treatment changes. Use paired per-case deltas and confidence intervals, plus negative controls and failure analysis. Planning quality: feasibility first; compare valid-plan cost against exact optimum for small cases or documented solver bound for larger cases. Report language-specific, cold-start and transfer effects, false-rule promotions, unsafe actions, leakage and costs. Do not claim 100% or statistical certainty from a small synthetic suite.

# 13. User interface and acceptance UX

## 13.1 Three required views

### A. Agent Workbench

- Multilingual text input; optional voice input with transcript confirmation.
- Authenticated tenant and role indicator.
- Parsed entities, ambiguities and no-confirm request visibly preserved.
- Permitted MCP tools, selected tools, latency, inputs and redacted outputs.
- Editable proposed draft with inventory/vehicle/time/source references, warnings and verifier verdict.
- Clear distinction among **suggestion**, **validated draft** and **exclusive simulated hold**.

### B. Experience & Improvement Lab

- Candidate lesson queue, source notes, evidence, contradictions, scope and risk class.
- Approve, narrow, reject, require evidence, challenge, expire and undo actions.
- Separate harness-patch subview: failure trace, original/candidate diff, paired probes, regression list, cost tradeoff and approval.
- No one-click automatic promotion of safety-impacting lessons without authorization.

### C. Benchmarks & Audit

- Arm A/B/C/D comparison with *counts and denominators*, not only percentages.
- Per-case result drill-down, safety failures, prompt-injection denials and concurrency verdicts.
- Tool precision/recall where meaningful, latency/cost distribution and model/harness versions.
- Exportable sanitized JSONL trace and benchmark manifest; live/replay labeling.
- Seed controls, company count, order count, scenario difficulty, generator version and snapshot hash; three distinct modes (sandbox, sealed, judge challenge).
- Per-specialist observable trace; proposed versus approved versus measured improvement; cold-start regional pack permissions and transfer-negative controls.

## 13.2 Product UX standards

A dispatcher should understand why a truck was suggested and why it might be unsafe without reading a model chain of thought. Show **short decision explanations based on observed evidence and explicit rules**, not private model reasoning. Error messages must be actionable (“which entrance?” or “vehicle schedule changed”) and the system must never silently imply an action was executed.

---

# 14. Functional requirements and acceptance gates

| ID | Requirement | Testable acceptance |
|---|---|---|
| FR-01 | English/Telugu/Roman-Telugu/mixed input | Measured examples in each mode with exact denominators |
| FR-02 | Muse is real runtime planner and lesson proposer | Provider call traces and model version present |
| FR-03 | MCP discovery and invocation | Real permitted tool schemas and successful calls |
| FR-04 | Conforming adapter normalization | A/B schema variants pass same contract tests |
| FR-05 | Ambiguous entity handling | Clarification before draft or a safe failure |
| FR-06 | Draft-only side effects | No exposed real dispatch/confirm capability |
| FR-07 | Deterministic capacity/dimension checks | Invalid mass/length/unit cases rejected |
| FR-08 | Atomic exclusive demo holds | Concurrent conflicts rejected; idempotency verified |
| FR-09 | Event trace and replay | Exact tool inputs, outputs, versions, evaluator result logged |
| FR-10 | Evidence-backed lesson proposal | Provenance, scope, confounders and contradictions saved |
| FR-11 | Conservative promotion | One failure cannot become a regional enforced ban |
| FR-12 | Manual reviewer decision | Approval, reject, edit scope and audit work correctly |
| FR-13 | Contradiction and lifecycle | Challenge/expiry/retirement/rollback tests pass |
| FR-14 | Harness patch boundaries | Only allowed metadata/guidance surface changes |
| FR-15 | Paired patch tests | Matched snapshots and immutable candidate/active diffs |
| FR-16 | Reject regressions | Candidate with unsafe or unauthorized regression cannot activate |
| FR-17 | Tenant and role enforcement | Attempts to bypass scope or impersonate reviewer denied |
| FR-18 | Prompt injection handling | Instructions embedded in tool results are not obeyed |
| FR-19 | Four-arm controlled evaluation | Runnable A/B/C/D with case-level results |
| FR-20 | Held-out contamination protections | No expected answers used in proposer or tuning |
| FR-21 | Hosted/replay mode | Fresh-browser test and clearly identified replay status |
| FR-22 | Spend and secrets | API caps, key redaction and no secret in git history |
| FR-23 | Licensing and originality | Clear upstream attribution and hackathon-only contribution ledger |
| FR-24 | Optional pack isolation | If shown, explicit opt-in/redaction/revocation tests pass |

All **FR-01 through FR-23** are part of the final P0 acceptance review. Where a noncritical capability cannot be finished, reduce the claimed P0 scope in README and demo rather than imply a pass. FR-24 is P1.

---

# 15. Non-functional requirements

| Dimension | Required behavior |
|---|---|
| Reliability | Bounded retries and idempotent writes; provider failures do not invent results |
| Reproducibility | Fixed seeds, fixture hashes, model/harness versions, repo commit and evaluator version |
| Security | Tenant isolation and server-side RBAC; no arbitrary code execution from model/tool text |
| Observability | Structured traces, timestamps, cost, token use, tool errors and state mutations |
| Auditability | Append-only review history; reversible changes preserve previous versions |
| Human control | Reviewer can reject and roll back changes; operator can cancel a draft |
| Performance | Record p50/p95 latency; no unsupported SLA claims during synthetic MVP |
| Cost | Per-run budget, global demo cap, mock/replay mode, spend reserve |
| Accessibility | Readable text/subtitles and clear error/warning labels for video and UI |
| Language | Telugu text round-trips UTF-8 correctly; romanized forms are not silently normalized to the wrong entity |
| Privacy | Entire hackathon dataset synthetic; no customer identities or secrets exposed |

---

# 16. Judge-facing demo design (180 seconds)

| Video time | Visible proof |
|---|---|
| **0:00–0:18** | Problem: a seemingly valid 32-ft truck cannot use one specific loading entrance |
| **0:18–0:45** | Muse receives Roman Telugu request; MCP calls; wrong/uncertain baseline draft with trace |
| **0:45–1:20** | Historical note mined; narrow candidate created; reviewer sees support and counterevidence |
| **1:20–1:45** | Reviewer confirms specifically scoped lesson; new task produces safer validated draft |
| **1:45–2:05** | Misleading habit is rejected and/or conflicting simulated hold is blocked |
| **2:05–2:25** | Harness guidance patch diff tested against baseline; gate decision shown |
| **2:25–2:48** | A/B/C/D benchmark with counts and no hidden safety defects; limitations stated |
| **2:48–3:00** | One-sentence contribution, Meta model roles, public repository and replay link |

**Demo rule:** Show only features genuinely built during the event; disclose original contributions versus libraries/research. Use captions for Telugu speech. A fast replay is acceptable only when labeled; the underlying code and full traces must remain available.

---

# 17. Delivery plan, dependencies and cut lines

| Date (IST) | Deliverable | Exit criterion |
|---|---|---|
| **Oct 28–29** | Freeze PRD, fixtures and eval cases; model/API smoke test | Reproducible baseline tool call and schema checks |
| **Oct 29–30** | MCP broker, adapter A/B fixture, LangGraph core and draft gate | Correct draft, wrong-unit rejection and conflict test |
| **Oct 30–31** | Notes, lesson miner, evidence view and state machine | Scoped lesson, false habit rejected, manual reviewer works |
| **Nov 1** | Harness patch proposer, sandbox probes and version rollback | One real candidate with paired outcomes and review verdict |
| **Nov 2** | Freeze/execute A/B/C/D benchmark; security and concurrency suite | All failures retained, denominators and costs known |
| **Nov 3** | UI finalization, public repo, README, hosted replay and video | Incognito walkthrough and clean install pass |
| **Nov 4** | Final audit, attribution, video/submission and contingency buffer | Submitted before deadline; no severe defects concealed |

## 17.1 Hard launch gates

The project must **not** demonstrate an action as safe if any of these tests fail: unauthorized executed action, cross-tenant data access, unapproved enforced lesson, duplicate exclusive hold, prompt-injection policy bypass, or unreviewed harness patch activation. If a critical failure remains, narrow the demonstration to read-only proposals and report the limitation clearly.

## 17.2 Feature cut order

Cut: upstream Harness² executor integration → third industry → optional domain pack → Spark Open comparison → voice → UI animation → extra tools. Preserve: true Muse/MCP calls, validated draft, two distinct learning loops, critical rejection tests, simple retrieval baseline, audit and complete demo.

## 17.3 Credit planning

The earlier overview reports approximately **$24 experimental spend** as of October 28 (roughly $15.3 Meta and $9.4 Baseten), but this is not a current billing balance. The participant guide describes **$150 Meta Model API credits** subject to claim status; partner allocation is selective. Reserve budget for final paired runs. Use local/mock traces for UI iteration, sampled development tests and per-run quota limits; do not burn credits on many candidate recursion branches.

---

# 18. Risks and mitigation

| Risk | Severity | Mitigation / go-no-go rule |
|---|---|---|
| Overclaiming arbitrary-data portability | Critical | Conforming adapter contract; negative test for incomplete schema |
| One incident becomes broad enforced rule | Critical | Advisory hypothesis, site scope, reviewer, evidence requirements |
| Conflict/double-booking | Critical | Transactional unique simulated holds and concurrency suite |
| Model-driven permission or policy bypass | Critical | Server-only roles and validators; patch surface allowlist |
| Cross-tenant leakage | Critical | Data partitions and explicit opt-in sharing; drop pack if unproven |
| Retrieval matches full learner | High | Publish B vs C honestly; change product claim if no incremental value |
| Overfitting/benchmark contamination | High | Locked split, separate proposer access and full logs |
| Google Harness² originality challenge | High | Explicit attribution and original contribution table |
| Meta use looks incidental | High | Real Muse planning/mining/diagnosis traces and measured role |
| Unrealistic synthetic history | High | Confounders, failed assumptions, hidden cases and practitioner feedback |
| Hosted model unavailable | Medium | Spend-capped live mode, local replay, clear labeling |
| Deadline scope inflation | High | Strict P0/P1, stop feature work after benchmark freeze |

---

# 19. Hackathon submission and originality checklist

- [ ] Public repository with commits showing work developed during the event.
- [ ] Accessible three-minute video showing only newly built functionality.
- [ ] Clear use of Meta models at runtime, with exact model ID and APIs called.
- [ ] README: setup, one-command seeded replay, architecture, data policy, experiments, honest limitations and license.
- [ ] Distinguish original Anubhav implementation from LangGraph, MCP/FastMCP, Google Harness² ideas or code, and any third-party datasets/assets.
- [ ] Include a benchmark manifest, frozen test results, denominators, adversarial failures, regression history and spend record.
- [ ] All company/person names and operational data fictional; no real credentials, secret git history or unauthorized assets.
- [ ] Submission date and website form rechecked; final upload confirmed before November 4, 9 PM ET.
- [ ] No claims of production safety, statistical proof or real-customer ROI unsupported by evidence.

## 19.1 Original contribution matrix

| Existing foundation | Attribution | Anubhav-specific contribution to demonstrate |
|---|---|---|
| Meta Muse models | Meta | Business planning, candidate lesson/patch proposal and multilingual execution |
| MCP | Model Context Protocol ecosystem | Tenant-governed semantic manifests and typed business adapter contracts |
| LangGraph | LangChain | Bounded state machine connecting verification and two learning loops |
| Google Harness² | Google Research | Bounded paired improvement adapted to verified MCP business actions; research method cited |
| Raw-note retrieval | Standard baseline | Evidence-aware promotion lifecycle, counterevidence, approval, expiry and rollback |
| SQLite simulator | Common tool | Reproducible multi-schema fixtures, transactional draft holds and state verifier |

---

# 20. Final release definition and product promise

**P0 is ready to submit** when: a new evaluator can install or open the demo; see a real Muse-planned MCP draft; observe a false operational rule rejected and a valid scoped one approved; inspect one attempted harness optimization and its gate; verify that conflicting holds are blocked; run A/B/C/D comparisons without gold leakage; and inspect exact sources, limitations and original contributions. If a component does not work, remove it from the final claim rather than presenting aspirational UI as functionality.

**90+ judging ambition:** The official rubric evaluates **Impact (30%), Use of Meta AI Tooling (25%), Technical Depth (20%) and Demo (25%)**. The goal is to build evidence that *could* justify an exceptionally high score in those categories. There is no known official 90-point finalist threshold, and no score in this PRD predicts ranking or prize outcome. The strongest proof is not a high self-score—it is a skeptical reviewer reproducing a genuine improvement over simpler alternatives while watching unsafe or unproven learning get rejected.

**Final one-line submission pitch:**

> **Anubhav uses Meta Muse and MCP to turn messy operational experience into reviewed, scoped business knowledge—and tests improvements to the agent's tool-use harness before trusting them on the next task.**

---

# Appendix A. Source and evidence ledger

**Project source files (supplied by the user):**

1. `Anubhav_overview.md` (28 Oct 2026): latest 3PL focus; reported interview; EXP-001–006 metrics and limitations.
2. `PRD_v1.1.md` (27 Oct 2026): older FMCG quotation focus; Muse, LangGraph, BigTool, MCP and evaluation infrastructure carried forward selectively.
3. `Anubhav_PRD_v2.0_Harness_MCP.md` (28 Oct 2026): predecessor architecture and boundaries; substantially refined in this final baseline.
4. `Anubhav_v2_Three_Judge_Report.md` (28 Oct 2026): simulated critique and scoring; not actual Meta judging.
5. `Details – Meta Global AI Developer Hackathon – Cerebral Valley(1).pdf`: organizer's participant guide, source of rules, dates, rubric and video requirements.
6. `Meta Global AI Developer Hackathon – Cerebral Valley.pdf`: public event overview and track definitions.

**Research and implementation references (public):**

- Google Research Harness² project: https://github.com/google-research/harness2
- Google Research Harness² paper: https://arxiv.org/abs/2610.14224
- Google Harness² experiments guide: https://github.com/google-research/harness2/blob/main/docs/EXPERIMENTS.md
- MCP tools specification, July 2026 version: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx
- LangGraph human-in-the-loop interrupts: https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/interrupts.mdx
- Hackathon event: https://cerebralvalley.ai/e/meta-ai-developer-hackathon

**Evidence discipline:** This PRD is an implementation specification. Earlier synthetic numbers are historical reported findings; new acceptance targets are not results. External research is cited as prior art. No real-world productivity effect, customer usage or final score is asserted as established.

# Appendix B. Minimal demo artifact structure

```text
anubhav/
  README.md
  LICENSES_AND_ATTRIBUTION.md
  app.py
  src/
    agent/             # Muse adapter, LangGraph state, prompts
    capabilities/      # typed manifests and broker
    adapters/          # adapter_a and adapter_b mapping
    policy/            # roles, invariants, draft holds
    learning_harness/  # patch proposal, paired probe, versioning
    learning_business/ # lesson miner, evidence, review lifecycle
    evaluation/        # independent scorer and replay
    observability/     # structured traces and spend guards
  fixtures/
    generator.py
    snapshots/
    dev_cases.jsonl
    locked_cases.jsonl  # accessible for judging, not for proposer runtime
    adversarial_cases.jsonl
  tests/
    test_mcp_contracts.py
    test_atomic_holds.py
    test_lessons.py
    test_harness_patches.py
    test_isolation.py
    test_end_to_end.py
  reports/
    final_benchmark.json
    final_benchmark.md
    experiment_manifest.json
    costs.csv
  docs/
    architecture.md
    submission_demo.md
    known_limitations.md
```

**Implementation discipline:** Each module must have a runnable contract test and meaningful logs; a clean public repository with fewer fully functioning components is preferable to a feature-rich but nonreproducible prototype.

---

**End of final design baseline — Anubhav PRD v3.0**


---

## Revision note — v3.1

This revision retains the v3.0 architecture, trust boundaries and two learning loops, and supersedes its two-schema, 64-task, dispatch-only assumptions. All new dataset counts are design targets, not generated results. The companion blueprint specifies generator scripts, integrity checks, review procedure and 100-case casebook.
