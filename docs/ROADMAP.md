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

Draft/approved/cancelled states, owner approval, editor/owner cancellation, append-only events, stale-version and contradictory-key rejection, reservation release, dependent schedule invalidation, protected review, and exact approved source-plan references.

### C4 — Reviewed preparation operations

Immutable resource calendars, complete occurrence/profile/request/response provenance, deterministic replay, schedule hashes, lifecycle states, protected final review, append-only schedule events, and user-confirmed task execution.

### C5 — Minimal-change preparation repair

Deterministic greedy repair, bounded exact comparator, immutable anchors, predecessor closure, capacity/window/deadline validation, structured conflicts, outcome partitions, hashes, authenticated API, offline CLI, and advisory non-persistence.

### C6 — Repair proposal and accepted-draft lifecycle

Immutable server-recomputed proposals, exact changed-task acknowledgements, one-new-draft-only acceptance, source immutability, separate method-aware owner approval, tamper/staleness checks, and append-only proposal/schedule evidence.

The **one-replacement-per-source invariant is implemented** through migration `20260802_0018`.

### C7 — Derivation and execution authority

**Schedule derivation evidence is implemented** through per-schedule and household-coverage endpoints plus a protected inspector.

**Task-execution eligibility is implemented** through a viewer-authorized endpoint and proactive frontend gate. Replaced sources remain readable but cannot receive new task events or completion.

### C8 — Proposal invalidation authority and administration

**Owner-only proposal invalidation is implemented** through an authenticated API, strict request contract, append-only event, server-observed stale reasons, exact idempotency, optimistic versioning, typed frontend client, protected owner administration workspace, editor/viewer read-only behavior, static contracts, Vitest coverage, and real PostgreSQL acceptance-versus-invalidation plus rejection-versus-invalidation races.

Invalidation cannot accept, persist, approve, execute, complete, or mutate a source schedule. It permanently closes only a `proposed` review record.

### C9 — Lowest-layer schedule completion authority

**Lowest-layer task terminality** is implemented in the exported `transition_schedule` service.

- Direct low-level completion requires all deterministic tasks to be completed or skipped.
- Existing error precedence and exact retries are preserved.
- Static validation forbids product code from importing the preserved implementation directly.
- A real PostgreSQL final-task-versus-schedule-completion race proves completion cannot commit ahead of the last task event.

### C10 — PostgreSQL lifecycle, migration, and transient-failure evidence

Configured real-database evidence includes:

- acceptance versus rejection, invalidation, source execution, source-plan cancellation, calendar supersession, and owner approval;
- final task completion versus schedule completion;
- discarded committed-response exact retry for acceptance, invalidation, and completion;
- a populated `0017 → 0018` migration rehearsal with 64 production-service acceptances, exact identity/hash preservation, catalog constraint verification, and lower-level bypass rollback;
- a real `statement_timeout` abort with SQLSTATE `57014` followed by successful same-key retry;
- a genuine PostgreSQL deadlock with one SQLSTATE `40P01` victim and one accepted replacement after exact retry;
- real **post-commit connection-loss recovery**: `pg_terminate_backend()` terminates the service backend after the acceptance transaction commits but before the first refresh/response; the failure maps to `database_commit_outcome_unknown`, independent reads prove one committed lifecycle, and the exact same-key retry returns it without duplication;
- a sanitized API boundary for retryable transaction SQLSTATEs and ambiguous connection outcomes;
- explicit `automatic_retry_performed=false` so the server never conceals duplicate or unknown commit outcomes.

Configured workflows retain JUnit and migration JSON evidence. None is represented as hosted green evidence until the exact current runs and artifacts are observed.

### C11 — Read-only support evidence export

A viewer-authorized and operator-CLI preparation schedule support export is implemented.

- Captures schedule provenance, lifecycle events, derivation, task-execution eligibility, deterministic task history, related repair proposals, acceptances, and proposal events.
- PostgreSQL uses a dedicated `REPEATABLE READ`, `SET TRANSACTION READ ONLY` snapshot and records `txid_current_snapshot()`.
- A canonical SHA-256 binds domain evidence and explicit non-claims while excluding transaction timestamps and snapshot metadata.
- The request session enforces viewer access and `404` non-disclosure; PostgreSQL repeats viewer authorization inside the exact export snapshot.
- The authenticated user ID is server-derived, while the operator CLI remains a separate privileged path.
- The protected browser requires explicit generation, clears stale scope, restores focus to generated evidence, and downloads the complete hash-addressed JSON without browser storage.
- SQLite/API regressions prove owner success, nonmember `404`, operator separation, complete evidence chains, and no mutation.
- A real PostgreSQL acceptance race proves an existing export retains its pre-acceptance snapshot while a fresh export sees the accepted replacement and a different evidence hash.

## P0 — Observe and repair exact hosted verification

1. Inspect exact latest `main` runs for SQLite, PostgreSQL, backend, frontend, OpenAPI, container, and focused repair workflows.
2. Inspect benchmark, JUnit, migration, and build artifacts.
3. Record exact commit SHA, run IDs, artifact IDs, durations, and failures.
4. Repair every failure without deleting, skipping, xfail-ing, weakening, or narrowing requirements.
5. Re-run failed jobs and verify the exact replacement run.
6. Do not report green until the exact current commit and artifacts are observed.

## P0 — Finish PostgreSQL operational recovery evidence

Remaining real-database work:

- connection loss while COMMIT acknowledgement itself is in flight, where neither client nor server response can safely establish the outcome;
- PostgreSQL primary loss/failover and pool-invalidated connection recovery;
- repeated serialization failures and a bounded, observable client retry policy;
- production-snapshot or production-scale migration rehearsal beyond the 64-lifecycle synthetic corpus;
- SQLSTATE, retry, ambiguous-outcome, pool, and lock-wait metrics and alerts.

Each probe must retain proposal, acceptance, schedule, event, version, hash, SQLSTATE, structured error, and retry identity evidence. The HTTP exception boundary must never perform automatic mutation retries.

## P0 — Complete authenticated browser and accessibility evidence

PostgreSQL-backed Playwright must cover signup/login/profile completion, household roles, plan review/approval/cancellation, occurrence confirmation, reviewed calendars, schedule persistence/approval, task execution/completion, advisory repair, proposal creation, acceptance, invalidation, method-aware approval, replacement eligibility, support-export download, stale versions, tamper, and `404` non-disclosure.

Accessibility evidence must include axe, keyboard-only operation, focus restoration, error summaries, live regions, labels, table semantics, reduced motion, zoom/reflow, and contrast.

## P0 — Harden support evidence packaging

The read-only snapshot, authorization boundary, viewer endpoint, CLI, and protected download workspace are implemented. Remaining:

- configurable field-level redaction and least-privilege support roles;
- signed/encrypted packages and independent verification tooling;
- secure object storage, retention, revocation, and deletion policies;
- support-case linkage and download audit events;
- pagination, streaming, and size limits for large histories;
- household-level multi-schedule bundles;
- production load, memory, and latency evidence.

## P1 — Execution-aware repair

A future engine must treat task events as immutable facts, preserve completed/skipped states and confirmed starts, prohibit moving executed work, distinguish historical actual work from remaining planned work, preserve dependency chronology, model in-progress/passive/supervision states, replan only remaining work, retain event identities, create a new draft without rewriting source history, expose structured infeasibility, and race execution onset against computation/proposal/acceptance/approval.

## P1 — Joint meal, inventory, shopping, and preparation repair

Jointly repair meals, servings, pantry allocations, reservations, shopping, leftovers, and tasks; preserve approved-plan/source history; release old reservations and create replacements only after explicit acceptance; add minimum-change objectives across meals, quantities, lots, purchases, and starts; and add partial repair with precise conflicts and exact/relaxed lower bounds.

## P1/P2 — Scheduling and optimization frontier

Optional interval-variable CP-SAT, MILP relaxation and infeasibility diagnosis, min-cost flow, LNS, conflict-targeted ruin-and-recreate, logic-based Benders, robust/stochastic durations/attendance/demand/prices, chance constraints, epsilon-constraint Pareto frontiers, unsat cores, and representative latency/memory/gap/failure reports.

## P2 — Evidence and normalization

Expand reviewed ingredient/conversion/profile/storage-policy coverage, multilingual/Indic normalization with retrieval/reranking/abstention, reviewed parse queues, signed evidence/trust/revocation, micronutrient uncertainty, and explicit blocking of time-temperature, microbial, medication, allergy, and clinical conclusions without qualified review and validated instrumentation.

## P2 — Inventory, shopping, and forecasting

Reviewed receipt/barcode OCR, lot split/merge, recall/quarantine, offline reconciliation, pending orders, lead times, delivery windows, substitutions, packs/prices, waste costs, stochastic service levels, exact lot-allocation explanation, classical and neural forecasting, hierarchical reconciliation, conformal calibration, drift/OOD detection, and closed-loop inventory metrics.

## P2 — Ranking, personalization, multimodal, and graph research

BPR, LightFM, two-tower retrieval, sequential and graph recommenders, calibrated constrained reranking, contextual bandits only after propensity validation, safe-policy-improvement gates, continual/federated personalization only with privacy/deletion/drift/rollback evidence, and research-only receipt/layout OCR, label/barcode extraction, food retrieval/segmentation, portion estimation, constrained extraction, graph substitutions, and multimodal retrieval.

## P2 — Security, privacy, operations, and release engineering

Verified email/password reset, MFA, token rotation/revocation, rate limiting, ownership recovery, archive/delete/export, audit retention, secret rotation, backup/PITR, PostgreSQL pooling/failover, logs/metrics/traces/SLOs, SBOM/scans, signed artifacts, canary/kill switches, incident response, rollback, and postmortems.

## P3 — High-risk blocked areas

Clinical nutrition, medication decisions, allergy-safety guarantees, microbial/contamination conclusions, autonomous appliance control, autonomous procurement/payment, food-safety certification, and verified sustainability claims remain disabled without specialist review, qualified data, consent, instrumentation, monitoring, rollback, and jurisdictional analysis.

## Non-negotiable release rules

- No clinical, allergy, medication, contamination, temperature, or food-safety claim without qualified evidence and review.
- No task execution, presence, appliance, or sensor inference from plans, schedules, or user-entered events.
- Advisory computation never reports acceptance or persistence.
- Proposal creation never creates a schedule.
- Proposal acceptance creates only one new draft and never implies approval, execution, or completion.
- Proposal invalidation creates no schedule and permanently prevents later acceptance.
- Repair-derived approval requires exact acceptance evidence and method-aware replay.
- Replaced sources remain readable but cannot receive new execution events.
- Every new completion transition requires explicit terminal task evidence at the lowest exported authority.
- Support export is read-only, hash-addressed, snapshot-authorized, and never upgrades user-entered evidence into execution or safety verification.
- Retryable or ambiguous database failures never trigger automatic server-side mutation retry; clients repeat the exact request with the same idempotency key.
- Frontend preflight never replaces server authority.
- No global-optimality or model-readiness claim from greedy/truncated search, catalog registration, importability, or synthetic tests.
- No green-build claim until exact hosted workflows and artifacts are observed.
- No force push, history rewrite, feature branch, or feature PR.
