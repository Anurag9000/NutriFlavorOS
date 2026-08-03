# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-03  
**Execution rule:** implement directly on `main` in coherent commits; keep code, tests, migrations, contracts, frontend clients, CI, and documentation synchronized; never rewrite history.  
**Current migration head:** `20260802_0018`  
**Current API:** `0.15.4`  
**Current OpenAPI contract:** `2026-08-03.2`

Catalog boundary: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

Configured code or tests are not executed evidence by themselves.

## Completed milestones

### C1–C5 — Transactional household planning and deterministic preparation

Authentication, household roles, pantry/leftover transactions, reservations, quantity-aware meal planning, plan lifecycle, reviewed preparation evidence, deterministic scheduling/replay, and minimal-change repair are implemented with optimistic versions, exact idempotency, provenance, hashes, and append-only evidence.

### C6 — Repair proposal and accepted-draft lifecycle

Immutable server-recomputed proposals, exact changed-task acknowledgement, one-new-draft-only acceptance, source immutability, separate method-aware owner approval, and append-only evidence are implemented. The **one-replacement-per-source invariant is implemented** by migration `20260802_0018` and a populated 64-lifecycle migration rehearsal.

### C7 — Derivation and execution authority

**Schedule derivation evidence is implemented** through per-schedule and household coverage endpoints plus a protected inspector.

**Task-execution eligibility is implemented** through a viewer endpoint and frontend gate. Replaced sources remain readable but cannot receive execution events or completion.

### C8 — Proposal invalidation authority

**Owner-only proposal invalidation is implemented** through API, typed client, protected workspace, exact version/idempotency, stale-reason capture, append-only events, role enforcement, and PostgreSQL terminal-outcome races.

### C9 — Lowest-layer schedule completion authority

**Lowest-layer task terminality** is implemented in exported `transition_schedule`. Direct completion requires explicit terminal task evidence, lower-level bypass is forbidden, and a PostgreSQL race proves completion cannot commit ahead of the final task event.

### C10 — PostgreSQL lifecycle, migration, and transient-failure evidence

Configured real-database evidence includes:

- lifecycle and dependency races for acceptance, rejection, invalidation, source execution, plan cancellation, calendar supersession, owner approval, and final-task completion;
- discarded-response exact recovery;
- populated `0017 → 0018` migration rehearsal with 64 production-service acceptances and bypass rollback;
- statement-timeout `57014` and genuine deadlock `40P01` recovery;
- real **post-commit connection-loss recovery** using `pg_terminate_backend` and exact same-key convergence;
- real **checked-out pool connection recovery** with `connection_invalidated=true`, zero pre-recovery mutation, a different backend PID, exact convergence, and `retry_safe=false`;
- **bounded exact serialization retry** with finite attempts, exponential backoff, immutable observations, unchanged idempotency key, and no automatic replay of ambiguous connections;
- a genuine `SERIALIZABLE` probe forcing **three consecutive `40001` aborts** before the fourth exact-key attempt creates exactly one acceptance and replacement;
- explicit `automatic_retry_performed=false` in the HTTP boundary.

### C11 — Read-only support evidence export

A viewer-authorized endpoint, operator CLI, typed GET-only client, and protected workspace provide hash-addressed schedule evidence. PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, snapshot-internal viewer authorization, and canonical hashing. A real concurrent-acceptance race proves snapshot consistency.

## P0 — Observe and repair exact hosted verification

1. Inspect exact latest `main` runs for SQLite, PostgreSQL, backend, frontend, OpenAPI, container, and focused repair workflows.
2. Inspect JUnit, migration, benchmark, and build artifacts.
3. Record exact commit SHA, run IDs, artifact IDs, durations, and failures.
4. Repair every failure without skip, xfail, weakening, narrowing, force push, or history rewrite.
5. Do not report green until exact current runs and artifacts are observed.

## P0 — Remaining PostgreSQL operational recovery

- Connection loss while COMMIT acknowledgement itself is in flight.
- PostgreSQL primary loss, replica promotion, DNS/service-discovery changes, and multi-node failover.
- Sustained pool exhaustion, timeout, recycle/lifetime behavior, process restart, and concurrent-load recovery.
- Production-snapshot or production-scale migration rehearsal beyond the 64-lifecycle corpus.
- SQLSTATE, retry, outcome-unknown, pool, and lock-wait metrics and alerts.

The HTTP server must never perform automatic mutation retries. Explicit callers may use bounded retry only when `retry_safe=true`; connection ambiguity remains `retry_safe=false` and requires authoritative same-key outcome recovery.

## P0 — Browser, accessibility, and support packaging

Add authenticated PostgreSQL-backed Playwright and axe evidence for the complete lifecycle; keyboard-only, focus, error-summary, live-region, label, table, reduced-motion, zoom/reflow, and contrast evidence; configurable redaction; least-privilege support roles; signed/encrypted packages; verification tooling; secure storage/retention/revocation; support-case and download audit linkage; streaming/size limits; household bundles; and production load evidence.

## P1 — Execution-aware repair

Treat task events as immutable facts; preserve completed/skipped states and confirmed starts; prohibit moving executed work; distinguish actual history from remaining plan; preserve chronology; model in-progress/passive/supervision states; replan only remaining work; retain event identities; create a new draft without rewriting source history; expose minimal conflicts; and race execution onset against proposal, acceptance, and approval.

## P1 — Joint meal, inventory, shopping, and preparation repair

Jointly repair meals, servings, pantry allocations, reservations, shopping, leftovers, and preparation tasks while preserving approved history and explicit human acceptance. Add minimum-change objectives, partial repair, exact/relaxed lower bounds, CP-SAT/MILP, LNS, ruin-and-recreate, and decomposition.

## P2 — Research and operations frontier

Expand reviewed evidence, multilingual normalization, receipt/barcode ingestion, recall/quarantine, lot split/merge, forecasting with uncertainty and drift/OOD, constrained ranking and personalization, security/privacy operations, backup/PITR, observability/SLOs, SBOM/scans, signed releases, canaries, rollback, and incident response.

## P3 — Blocked high-risk areas

Clinical nutrition, medication decisions, allergy-safety guarantees, contamination or food-safety conclusions, autonomous appliance control, autonomous procurement/payment, and verified sustainability claims remain disabled without specialist review, qualified data, consent, instrumentation, monitoring, rollback, and jurisdictional analysis.

## Non-negotiable release rules

- Advisory computation never reports acceptance or persistence.
- Proposal creation never creates a schedule.
- Acceptance creates one new draft and never implies approval, execution, or completion.
- Invalidation creates no schedule and permanently prevents later acceptance.
- Repair-derived approval requires exact acceptance evidence and method-aware replay.
- Replaced sources remain readable but cannot receive new execution events.
- Completion requires explicit task terminality at the lowest exported authority.
- Support export is read-only, hash-addressed, snapshot-authorized, and never upgrades user-entered evidence into execution or safety verification.
- `retry_safe=true` is reserved for proven transaction aborts; connection ambiguity remains `retry_safe=false`.
- The server always reports `automatic_retry_performed=false`.
- Frontend preflight never replaces server authority.
- No clinical, food-safety, global-optimality, model-readiness, or green-build claim without exact supporting evidence.
- No force push, history rewrite, feature branch, or feature PR.
