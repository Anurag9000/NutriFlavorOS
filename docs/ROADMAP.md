# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-03  
**Execution rule:** implement directly on `main` in coherent commits; keep code, tests, migrations, contracts, frontend clients, CI, and documentation synchronized; never rewrite history.  
**Current migration head:** `20260802_0018`  
**Current API:** `0.15.3`  
**Current OpenAPI contract:** `2026-08-03.1`

Current catalog boundary: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

A class, endpoint, fixture, configured workflow, or catalog row is not completion or executed evidence by itself.

## Completed architecture milestones

### C1 — Transactional household platform

Authentication, explicit profile completion, household roles, hashed invitations, transactional pantry/leftovers, reservations, optimistic versions, exact idempotency, and PostgreSQL race probes.

### C2 — Quantity-aware meal planning

Deterministic horizon planning, hard restrictions, household target aggregation, pantry-aware objectives, persisted plans, shopping reconciliation, reservations, batch grouping, Pareto, optional CP-SAT/MILP, robust scenarios, and exact comparators.

### C3 — Human-reviewed plan lifecycle

Draft/approved/cancelled states, owner approval, editor/owner cancellation, append-only events, stale-version/contradictory-key rejection, reservation release, dependent schedule invalidation, protected review, and exact approved source-plan references.

### C4 — Reviewed preparation operations

Immutable resource calendars, complete occurrence/profile/request/response provenance, deterministic replay, schedule hashes, lifecycle states, protected final review, append-only schedule events, and user-confirmed task execution.

### C5 — Minimal-change preparation repair

Deterministic greedy repair, bounded exact comparator, immutable anchors, predecessor closure, capacity/window/deadline validation, structured conflicts, outcome partitions, hashes, authenticated API, offline CLI, and advisory non-persistence.

### C6 — Repair proposal and accepted-draft lifecycle

Immutable server-recomputed proposals, exact changed-task acknowledgements, one-new-draft-only acceptance, source immutability, separate method-aware owner approval, tamper/staleness checks, and append-only proposal/schedule evidence.

The one-replacement-per-source invariant is implemented through migration `20260802_0018`.

### C7 — Derivation and execution authority

Schedule derivation evidence is implemented through per-schedule and household-coverage endpoints plus a protected inspector.

Task-execution eligibility is implemented through a viewer-authorized endpoint and proactive frontend gate. Replaced sources remain readable but cannot receive new task events or completion.

### C8 — Proposal invalidation authority and administration

Owner-only proposal invalidation is implemented through an authenticated API, strict request contract, append-only event, server-observed stale reasons, exact idempotency, optimistic versioning, typed frontend client, protected owner administration workspace, editor/viewer read-only behavior, static contracts, Vitest coverage, and real PostgreSQL acceptance-versus-invalidation plus rejection-versus-invalidation races.

Invalidation cannot accept, persist, approve, execute, complete, or mutate a source schedule. It permanently closes only a `proposed` review record.

### C9 — Lowest-layer schedule completion authority

**Lowest-layer task terminality** is implemented in the exported `transition_schedule` service.

- Direct low-level `COMPLETED` calls require all deterministic tasks to be explicitly completed or skipped.
- The public authority facade preserves the established operations implementation and existing error precedence.
- The named completion service is a delegate, not a second proof/commit path.
- Static validation forbids product code from importing the preserved implementation directly.
- The complete historical operations test corpus is retained, with the obsolete implicit-completion case replaced by explicit terminality evidence.
- A real PostgreSQL final-task-versus-schedule-completion race proves completion cannot commit ahead of the last task event.

### C10 — PostgreSQL lifecycle, migration, and transient-failure evidence

The configured real-database evidence now includes:

- acceptance versus rejection, acceptance versus invalidation, and rejection versus invalidation;
- source-plan cancellation versus acceptance and repaired owner approval;
- calendar supersession versus acceptance and repaired owner approval;
- final task completion versus schedule completion;
- discarded committed-response exact retry for acceptance, invalidation, and completion;
- a populated `0017 → 0018` migration rehearsal with 64 production-service acceptances, exact identity/hash preservation, catalog constraint verification, and lower-level bypass rollback;
- a real `statement_timeout` abort with SQLSTATE `57014` followed by successful same-key retry;
- a genuine PostgreSQL row-lock/advisory-lock deadlock with exactly one SQLSTATE `40P01` victim and one accepted replacement after exact retry;
- a sanitized API boundary for retryable transaction SQLSTATEs and ambiguous connection outcomes;
- explicit `automatic_retry_performed=false` so the server never conceals duplicate or unknown commit outcomes.

Configured workflows retain JUnit and migration JSON evidence. None is represented as hosted green evidence until the exact current runs and artifacts are observed.

### C11 — Read-only support evidence export

A viewer-authorized and operator-CLI preparation schedule support export is implemented.

- Captures schedule provenance, lifecycle events, derivation, task-execution eligibility, deterministic task history, related repair proposals, acceptances, and proposal events.
- PostgreSQL uses a dedicated `REPEATABLE READ`, `SET TRANSACTION READ ONLY` snapshot and records `txid_current_snapshot()`.
- A canonical SHA-256 binds domain evidence and explicit non-claims while excluding transaction timestamps/snapshot metadata.
- The export reports `mutation_performed=false`, `actual_execution_verified=false`, and `food_safety_verified=false`.
- Authentication plus household viewer access and `404` non-disclosure are enforced by the API.
- The CLI writes atomically and returns structured database/resource errors.
- SQLite regressions verify original and accepted-repair chains, source/replacement perspectives, hashes, and no mutation.
- A real PostgreSQL acceptance race proves an existing export retains its pre-acceptance snapshot while a fresh export sees the accepted replacement and a different evidence hash.

## P0 — Observe and repair exact hosted verification

1. Inspect exact latest `main` runs for SQLite, PostgreSQL, backend, frontend, OpenAPI, container, and focused repair workflows.
2. Inspect benchmark, JUnit, migration, and build artifacts.
3. Record exact commit SHA, run IDs, artifact IDs, durations, and failures.
4. Repair every failure without deleting, skipping, xfail-ing, weakening, or narrowing requirements.
5. Re-run failed jobs and verify the exact replacement run.
6. Do not report green until the exact current commit and artifacts are observed.

## P0 — Complete execution eligibility evidence

Backend, frontend, and support-export eligibility evidence are implemented. Remaining:

- authenticated PostgreSQL-backed browser scenarios;
- replacement selection across draft/approved/invalidated/cancelled/completed/missing states;
- accessibility evidence for blocked-state alerts and disabled controls;
- operational metrics and support dashboards;
- continued server-side mutation authority against stale clients and races.

## P0 — Finish PostgreSQL operational recovery evidence

Remaining real-database work:

- connection loss during or immediately after commit with exact same-key outcome recovery;
- PostgreSQL failover and pool-invalidated connection recovery;
- repeated serialization failures and a bounded, observable client retry policy;
- production-snapshot or production-scale migration rehearsal beyond the 64-lifecycle synthetic corpus;
- SQLSTATE, retry, ambiguous-outcome, pool, and lock-wait metrics/alerts.

Each probe must retain final proposal, acceptance, schedule, event, version, hash, SQLSTATE, structured error, and retry identity evidence. The HTTP exception boundary must never perform automatic mutation retries.

## P0 — Harden support evidence packaging

The read-only snapshot and viewer endpoint are implemented. Remaining:

- configurable field-level redaction and least-privilege support roles;
- signed/encrypted packages and verification tooling;
- secure object storage, retention, revocation, and deletion policies;
- support-case linkage and download audit events;
- pagination/streaming/size limits for large execution histories;
- household-level multi-schedule evidence bundles;
- production load, memory, and latency evidence.

## P1 — Authenticated browser and accessibility evidence

PostgreSQL-backed Playwright should cover signup/login/profile completion, household roles, plan review/approval/cancellation, occurrence confirmation, reviewed calendars, schedule persistence/approval, task execution/completion, advisory repair, proposal creation, acceptance, invalidation, method-aware approval, replacement eligibility, support-export download, stale versions, tamper, and `404` non-disclosure.

Accessibility evidence must include axe, keyboard-only operation, focus restoration, error summaries, live regions, labels, table semantics, reduced motion, zoom/reflow, and contrast.

## P1 — Execution-aware repair

The current ordinary repair correctly abstains after source task history begins. A future engine must:

- treat all task events as immutable facts;
- preserve completed/skipped states and confirmed starts;
- prohibit moving executed work;
- distinguish historical actual work from remaining planned work;
- preserve dependency chronology;
- handle in-progress/passive/supervision states explicitly;
- replan only remaining work;
- retain event IDs, versions, actors, timestamps, and fingerprints;
- create a new draft without rewriting source history;
- expose structured infeasibility/minimal conflicts;
- race execution onset against computation, proposal creation, acceptance, and approval.

## P1 — Joint meal, inventory, shopping, and preparation repair

- Jointly repair meals, servings, pantry allocations, reservations, shopping, leftovers, and tasks.
- Preserve approved-plan/source-schedule history.
- Release old reservations and create replacements only after explicit acceptance.
- Add minimum-change objectives across meals, quantities, lots, purchases, and starts.
- Add partial repair with precise conflicts.
- Add CP-SAT/MILP lower bounds, LNS, ruin-and-recreate, and decomposition.

## P1/P2 — Scheduling and optimization frontier

Optional interval-variable CP-SAT, MILP relaxation/infeasibility diagnosis, min-cost flow, LNS, conflict-targeted ruin-and-recreate, logic-based Benders, robust/stochastic durations/attendance/demand/prices, chance constraints, epsilon-constraint Pareto frontiers, unsat cores, and representative latency/memory/gap/failure reports.

## P2 — Evidence and normalization

Expand reviewed ingredient/conversion/profile/storage-policy coverage, multilingual/Indic normalization with retrieval/reranking/abstention, reviewed parse queues, signed evidence/trust/revocation, micronutrient uncertainty, and explicit blocking of time-temperature/microbial/medication/allergy/clinical conclusions without qualified review and validated instrumentation.

## P2 — Inventory and shopping

Reviewed receipt/barcode OCR, lot split/merge, recall/quarantine, offline reconciliation, pending orders, lead times, delivery windows, substitutions, packs/prices, waste costs, stochastic service levels, and exact lot-allocation explanation.

## P2 — Forecasting

Last-value, drift, SBA, ADIDA, IMAPA, Theta, ETS, ARIMA, hierarchical reconciliation, quantile/conformal intervals, DeepAR, N-BEATS/N-HiTS, TFT, PatchTST, change-point/drift/OOD/abstention, temporal splits, intermittent strata, calibration, and closed-loop inventory metrics.

## P2 — Ranking and personalization

BPR, LightFM, two-tower retrieval, SASRec, graph recommenders, calibrated constrained reranking, contextual bandits only after propensity validation, doubly robust off-policy evaluation, safe-policy-improvement gates, and continual/federated personalization only with privacy/deletion/drift/subgroup/rollback evidence.

## P2 — Vision, OCR, multimodal, and graph research

Research-only until licensed data, uncertainty, OOD, subgroup, latency, privacy, monitoring, and rollback gates pass: receipt/layout OCR, label/barcode extraction, food retrieval/segmentation, portion/nutrition estimation, constrained extraction, graph substitutions, and multimodal recipe/ingredient retrieval.

## P2 — Security, privacy, operations, and release engineering

Verified email/password reset, MFA, token rotation/revocation, rate limiting, ownership recovery, archive/delete/export, audit retention, secret rotation, backup/PITR, PostgreSQL pooling/failover, logs/metrics/traces/SLOs, SBOM/scans, signed artifacts, canary/kill switches, incident/rollback/postmortems.

## P3 — High-risk blocked areas

Clinical nutrition, medication decisions, allergy-safety guarantees, microbial/contamination conclusions, autonomous appliance control, autonomous procurement/payment, food-safety certification, and verified sustainability claims remain disabled without specialist review, qualified data, consent, instrumentation, monitoring, rollback, and jurisdictional analysis.

## Non-negotiable release rules

- No clinical, allergy, medication, contamination, temperature, or food-safety claim without qualified evidence/review.
- No task execution, presence, appliance, or sensor inference from plans, schedules, or user-entered events.
- Advisory computation never reports acceptance or persistence.
- Proposal creation never creates a schedule.
- Proposal acceptance creates only one new draft and never implies approval/execution/completion.
- Proposal invalidation creates no schedule and permanently prevents later acceptance.
- Repair-derived approval requires exact acceptance evidence and method-aware replay.
- Replaced sources remain readable but cannot receive new execution events.
- Every new schedule completion transition requires explicit terminal task evidence at the lowest exported authority.
- Support export is read-only, hash-addressed, and never upgrades user-entered evidence into execution or safety verification.
- Retryable or ambiguous database failures never trigger an automatic server-side mutation retry; clients repeat the exact request with the same idempotency key.
- Frontend preflight never replaces server authority.
- No global-optimality or model-readiness claim from greedy/truncated search, catalog registration, importability, or synthetic tests.
- No green-build claim until exact hosted workflows/artifacts are observed.
- No force push, history rewrite, feature branch, or feature PR.
