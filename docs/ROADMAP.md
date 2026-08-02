# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-02  
**Execution rule:** implement directly on `main` in coherent commits; keep code, tests, migrations, contracts, frontend clients, CI, and documentation synchronized; never rewrite history.  
**Current migration head:** `20260802_0018`  
**Current API:** `0.15.1`  
**Current OpenAPI contract:** `2026-08-02.11`

Current catalog boundary: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

A class, endpoint, fixture, configured workflow, or catalog row is not completion or executed evidence by itself.

## Completed architecture milestones

### C1 — Transactional household platform

Authentication, explicit profile completion, household roles, hashed invitations, transactional pantry/leftovers, reservations, optimistic versions, exact idempotency, and PostgreSQL race probes.

### C2 — Quantity-aware meal planning

Deterministic horizon planning, hard restrictions, household target aggregation, pantry-aware objectives, persisted plans, shopping reconciliation, reservations, batch grouping, Pareto, optional CP-SAT/MILP, robust scenarios, and exact comparators.

### C3 — Human-reviewed plan lifecycle

Draft/approved/cancelled states, owner approval, editor/owner cancellation, append-only events, stale-version and contradictory-key rejection, atomic reservation release, dependent schedule invalidation, protected review, and exact approved source-plan references.

### C4 — Reviewed preparation operations

Immutable resource calendars, complete occurrence/profile/request/response provenance, deterministic replay, schedule hashes, draft/approved/invalidated/completed/cancelled lifecycle, protected final review, append-only schedule events, and user-confirmed task execution.

### C5 — Minimal-change preparation repair

Deterministic greedy repair, bounded exact comparator, immutable anchors, predecessor closure, capacity/window/deadline validation, structured conflicts, outcome partitions, canonical hashes, authenticated API, offline CLI, and advisory non-persistence.

### C6 — Repair proposal and accepted-draft lifecycle

Immutable server-recomputed proposals, exact changed-task acknowledgements, one-new-draft-only acceptance, source immutability, separate method-aware owner approval, tamper/staleness checks, and append-only proposal/schedule evidence.

The one-replacement-per-source invariant is implemented through migration `20260802_0018`: multiple advisory proposals may exist for one source version, but only one may create the accepted replacement.

### C7 — Derivation and execution authority

Schedule derivation evidence is implemented through per-schedule and household-coverage endpoints plus a protected inspector.

Task-execution eligibility is implemented through a viewer-authorized endpoint and proactive frontend gate. A source with an accepted replacement remains readable but cannot receive new task events or completion. Exact proposal, acceptance, and replacement identities are exposed.

## P0 — Observe and repair exact hosted verification

1. Inspect the exact latest `main` runs for SQLite, PostgreSQL, backend, frontend, OpenAPI, container, and focused repair workflows.
2. Inspect retained benchmark, JUnit, migration, and build artifacts.
3. Record exact commit SHA, workflow/run IDs, artifact IDs, durations, and failures.
4. Repair every failure without deleting, skipping, xfail-ing, weakening, or narrowing a requirement.
5. Re-run failed jobs and verify the exact replacement run.
6. Do not report green until the exact current commit and artifacts are observed.

## P0 — Finish lowest-layer task terminality authority

The product endpoint is guarded and static analysis blocks new product-level low-level completion calls. The remaining compatibility boundary is the historical generic transition service.

1. Inventory every direct schedule completion caller.
2. Move task-terminality assertion into the lowest authoritative transition layer.
3. Migrate all internal tests/callers through that layer.
4. Remove or narrowly encapsulate compatibility behavior.
5. Add direct-service, API, stale-version, duplicate-key, malformed-history, and PostgreSQL-race tests.
6. Retain the non-claim that task events are user-entered evidence rather than observed execution.

## P0 — Complete execution eligibility evidence

Backend and frontend eligibility are implemented. Remaining work:

- add authenticated PostgreSQL-backed browser scenarios;
- verify selection switches correctly to an eligible approved replacement;
- cover replacement still in draft, invalidated, cancelled, completed, or missing states;
- add accessibility evidence for blocked-state alerts and disabled controls;
- include eligibility status in export/support tooling and operational metrics;
- retain server-side mutation guards as authority even when the client preflights eligibility.

## P0 — PostgreSQL lifecycle and recovery evidence

Extend real-database probes for:

- source plan cancellation racing proposal acceptance;
- target calendar supersession racing acceptance or approval;
- proposal invalidation racing acceptance once invalidation tooling exists;
- unknown commit outcome and exact retry recovery;
- connection loss after flush but before response;
- statement timeout/deadlock retry behavior;
- migration `0018` on representative historical data volumes;
- concurrent export/support reads during lifecycle mutation.

Every probe must retain final proposal, acceptance, schedule, event, version, hash, and structured-error evidence.

## P1 — Authenticated browser and accessibility evidence

PostgreSQL-backed Playwright should cover:

1. signup, login, and profile completion;
2. household creation, invitation, and role boundaries;
3. plan generation, review, approval, and cancellation;
4. occurrence confirmation;
5. reviewed calendar creation and activation;
6. schedule persistence, draft review, owner approval, and events;
7. user-confirmed task start/complete/skip and guarded schedule completion;
8. advisory repair and immutable proposal creation;
9. exact changed-task acknowledgement and one-new-draft acceptance;
10. separate method-aware owner approval;
11. source replacement eligibility block and replacement selection;
12. plan/calendar/source staleness, tamper, version conflicts, and `404` non-disclosure.

Accessibility evidence must include axe, keyboard-only operation, focus restoration, error summaries, live regions, labels, table semantics, reduced motion, zoom/reflow, and contrast.

## P1 — Execution-aware repair

The current ordinary repair correctly abstains when source task history exists. A future execution-aware engine must:

- treat every task event as immutable historical fact;
- preserve completed/skipped states and confirmed starts;
- prohibit moving executed work;
- distinguish actual historical work from remaining planned work;
- preserve dependency chronology;
- handle in-progress tasks, passive waiting, and supervision handoffs explicitly;
- replan only remaining work;
- retain event IDs, versions, actors, timestamps, and fingerprints;
- create a new draft without rewriting source history;
- surface structured infeasibility and minimal conflicts;
- race execution onset against computation, proposal creation, acceptance, and approval.

## P1 — Joint meal, inventory, shopping, and preparation repair

- Jointly repair meal choices, servings, pantry allocations, reservations, shopping needs, leftovers, and preparation tasks.
- Preserve approved-plan and source-schedule history.
- Release old reservations and create replacements atomically only after explicit acceptance.
- Add minimum-change objectives across meals, quantities, lots, purchases, and task starts.
- Add partial repair with precise conflict explanations.
- Add CP-SAT/MILP lower bounds, large-neighborhood search, ruin-and-recreate, and decomposition.

## P1 — Proposal administration and support

- Add explicit server-authoritative invalidation for stale proposed records.
- Add role/actor/reason/idempotency/version contracts.
- Preserve append-only events and exact historical readability.
- Add support search by source, proposal, acceptance, replacement, actor, hash, and time.
- Add evidence export packages without exposing secrets or internal-only data.

## P1/P2 — Scheduling and optimization frontier

- Optional interval-variable CP-SAT model.
- MILP relaxation and infeasibility diagnosis.
- Min-cost flow for allocation/shopping subproblems.
- Large-neighborhood search seeded by deterministic repair.
- Conflict-targeted ruin-and-recreate.
- Logic-based Benders decomposition between meal choice and kitchen scheduling.
- Robust/stochastic duration, attendance, demand, and price scenarios.
- Chance-constrained service and waste targets.
- Epsilon-constraint Pareto frontiers.
- Unsat cores or minimal conflict sets.
- Representative latency, memory, optimality-gap, and failure-rate reports.

## P2 — Evidence and normalization

- Expand reviewed ingredient, conversion, preparation-profile, and storage-policy coverage with explicit denominators.
- Add multilingual/Indic ingredient normalization with retrieval, reranking, and abstention.
- Add reviewed parse queues and adjudication.
- Add signed evidence documents, trust roots, revocation, and retained immutable objects.
- Add micronutrient normalization and uncertainty.
- Keep time-temperature, microbial, medication, allergy, and clinical conclusions blocked without qualified review and validated instrumentation.

## P2 — Inventory and shopping

- Receipt/barcode OCR with reviewed correction.
- Lot split/merge, recall/quarantine, and offline reconciliation.
- Pending orders, lead times, delivery windows, substitutions, minimum packs, and prices.
- Waste/disposal costs and stochastic service-level optimization.
- Exact lot-allocation explanation and bulk reconciliation.

## P2 — Forecasting

- Last-value, drift, SBA, ADIDA, IMAPA, Theta, ETS, and ARIMA baselines.
- Hierarchical reconciliation across ingredient, recipe, household, and horizon levels.
- Quantile regression and rolling/split conformal intervals.
- DeepAR, N-BEATS/N-HiTS, TFT, and PatchTST research baselines.
- Change-point, drift, OOD, and abstention models.
- Temporal splits, rolling origin, intermittent-demand strata, interval coverage, calibration, and closed-loop inventory metrics.

## P2 — Ranking and personalization

- BPR, LightFM, two-tower retrieval, SASRec, and graph recommenders.
- Calibrated constrained reranking for restrictions, pantry, cuisine, repetition, and diversity.
- Contextual bandits only after propensity validation.
- Doubly robust off-policy evaluation and safe-policy-improvement gates.
- Continual/federated personalization only with privacy, deletion, drift, subgroup, and rollback evidence.

## P2 — Vision, OCR, multimodal, and graph research

Research-only until licensed data, uncertainty, OOD, subgroup, latency, privacy, monitoring, and rollback gates pass:

- receipt/layout OCR;
- label/barcode extraction;
- food image retrieval and segmentation;
- portion/nutrition estimation;
- constrained structured extraction;
- graph-based substitutions with hard evidence/restriction filters;
- multimodal recipe/ingredient retrieval.

## P2 — Security, privacy, and identity lifecycle

- Verified email and password reset.
- MFA and recovery.
- Refresh-token rotation/revocation.
- Rate limiting and abuse controls.
- Ownership transfer/recovery.
- Household archive/delete.
- Complete export/delete and research-data deletion propagation.
- Audit-log access/retention and secret rotation.

## P2 — Operations and release engineering

- Backup/restore and point-in-time recovery.
- PostgreSQL pooling, replicas, failover, and large-table migration rehearsal.
- Structured logs, metrics, traces, SLOs, alerts, and runbooks.
- SBOM, dependency/container/static/dynamic scans, signed artifacts, and provenance attestations.
- Canary/shadow/kill-switch contracts for future online models.
- Incident, rollback, and postmortem evidence.

## P3 — High-risk blocked areas

These remain disabled by default and require specialist review, qualified data, explicit consent, validated instrumentation, monitoring, rollback, and jurisdictional analysis:

- clinical nutrition or medical personalization;
- medication interaction decisions;
- allergy-safety guarantees;
- microbial or contamination conclusions;
- autonomous appliance control;
- autonomous procurement/payment;
- food-safety certification;
- sustainability claims presented as verified consumer facts.

## Non-negotiable release rules

- No clinical, allergy, medication, contamination, temperature, or food-safety claim without appropriate evidence and qualified review.
- No task execution, presence, appliance, or sensor inference from plans, schedules, or user-entered events.
- Advisory repair computation can never report acceptance or persistence.
- Proposal creation can never create a schedule.
- Proposal acceptance can create only one new draft and can never imply approval, execution, or completion.
- Repair-derived approval requires exact acceptance evidence and method-aware replay.
- Replaced source schedules remain readable but cannot receive new execution events.
- Frontend eligibility is preflight UX; server mutation guards remain authoritative.
- No global-optimality claim for greedy or truncated search.
- No readiness claim from catalog registration, importability, or synthetic tests.
- No green-build claim until exact hosted workflows and artifacts are observed.
- No force push or history rewrite.
- All implementation belongs on `main`; legacy branch refs must contain no unique work and should be deleted when branch deletion is available.
