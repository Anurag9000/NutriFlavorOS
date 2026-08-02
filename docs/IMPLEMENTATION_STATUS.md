# NutriFlavorOS Implementation Status

**Status date:** 2026-08-02  
**Development policy:** coherent direct commits to `main`; no feature pull requests or development branches; no history rewriting.  
**Database migration head:** `20260802_0014`  
**API version:** `0.12.1`  
**OpenAPI release contract:** `2026-08-02.6`  
**Food-evidence frontend binding contract:** `2026-08-01.2`  
**Preparation-operations frontend binding contract:** `2026-08-02.4`  
**Household-plan frontend binding contract:** `2026-08-02.4`  
**Effective research catalog:** `2026-08-01.3`

Governed research inventory:

- **37 task contracts**;
- **30 dataset families**;
- **75 model or algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

A class, endpoint, committed test, configured workflow, synthetic fixture, or catalog row is not by itself a readiness, quality, clinical-validation, food-safety, execution-verification, or green-build claim.

## Identity and household collaboration

### Implemented

- Argon2 password hashing, signed JWTs, issuer/audience/timing claims, and refusal of weak signing secrets.
- Explicit profile-completion state; signup does not fabricate physiology or nutrition targets.
- Owner, editor, and viewer household roles with `404` non-disclosure.
- Hashed email-bound, expiring, single-use invitations with replacement, revocation, exact-email acceptance, retries, and locking.
- Linked and planning-only members with explicit restrictions and serving multipliers.

### Remaining

- Verified email, password reset, MFA, token rotation/revocation, authentication rate limits, ownership transfer, household archive/delete, complete export/delete, and support tooling.

## Database, migrations, and release integrity

### Implemented

- Transactional SQLite and PostgreSQL paths.
- One linear Alembic chain through `20260802_0014`.
- Runtime startup verifies the exact revision and required tables.
- Fresh SQLite and PostgreSQL migration jobs.
- Database constraints for inventory, roles, evidence, plans, calendars, schedules, replay provenance, lifecycle transitions, task execution, idempotency, and optimistic versions.
- Additive ORM mappings load during package initialization and match Alembic indexes/constraints.
- Repository, Alembic, catalog, OpenAPI, frontend-release, preparation-repair, and execution contracts are mechanically validated.

### Remaining

- Backup/restore, point-in-time recovery, large-table rehearsal, retention/purge, hosted pooling/replicas, failover, and disaster-recovery evidence.

## Pantry, leftovers, inventory, and reservations

### Implemented

- Versioned pantry lots with quantity intervals, units, source, expiry/open times, and metadata.
- Append-only purchase, consumption, discard, adjustment, leftover, reservation, and reservation-commit events.
- Negative-stock and incompatible-unit prevention.
- FEFO allocation, expired-stock exclusion, reservation lifecycle, overbooking prevention, exact idempotency, and PostgreSQL races.
- Shopping reconciliation and batch-preparation grouping.
- Plan cancellation releases active reservations atomically.

### Remaining

- Reviewed cross-unit allocation in every path, receipt/barcode import, lot split/merge UX, recall/quarantine, offline conflict handling, variable lead time, pending orders, and bulk reconciliation.

## Immutable food and preparation evidence

### Implemented

- Immutable conversion, storage-policy, and preparation-profile histories.
- Natural/version keys, source, reviewer, UTC review time, SHA-256, supersession, evidence state, and active uniqueness.
- Exact reviewed conversion application and exact leftover-to-policy links.
- Typed dry-run/apply/reapply imports, manifests, lifecycle actions, locks, and concurrency probes.
- Preparation profiles with serving range, task DAG, duration interval, resource demand, active-work/supervision declarations, and immutable provenance.

### Remaining or blocked

- Broader reviewed coverage, signed documents/trust roots, production object retention, micronutrient normalization, reviewed parse workflow, time-temperature instrumentation, and sensors. Autonomous safe-to-eat decisions remain prohibited.

## Meal planning and household plan lifecycle

### Implemented

- Conservative parsing, serving scaling, reviewed conversions, and hard restrictions before optimization.
- Deterministic household horizon planning with nutrition, preference, cost, variety, repetition, pantry, and cuisine objectives.
- Household target aggregation, persisted plans, warnings, diagnostics, shopping reconciliation, and optional reservations.
- Pareto, optional CP-SAT/MILP, robust scenarios, and exact small-instance comparators.
- Migration-backed `draft`, `approved`, and `cancelled` plan states with optimistic versions and append-only events.
- Owner approval; editor/owner cancellation; exact retries; stale and contradictory reuse rejection.
- Atomic reservation release and dependent schedule invalidation on cancellation.
- Protected plan-review workspace.
- Approved-plan occurrence candidates and explicit confirmation with serving-count semantics, separate batch scale, explicit deadlines, reviewed-profile compatibility, and canonical non-persisted occurrence documents.

### Remaining

- Standalone immutable confirmed-occurrence records.
- Joint meal/preparation optimization and joint plan/schedule repair.
- Exact lot allocation, Pareto UX, robust/chance-constrained planning, and representative-scale benchmarks.

## Deterministic preparation scheduling and repair

### Implemented scheduling

- Strict tasks, resources, capacities, dependencies, deadlines, and provenance.
- Multi-window availability with overlap/horizon checks and gap containment.
- Cumulative resource capacity, dependency propagation, utilization, peaks, critical path, and structured infeasibility.
- Reviewed-profile compile-and-schedule path.
- Bounded exact comparator and metamorphic tests.

### Implemented repair

- Strict previous-request, previous-response, and revised-request contracts.
- Validation that the previous deterministic response is complete and matches its request task set and operational snapshots.
- Deterministic `greedy_min_change` repair that tries prior placements first and uses stable displacement/task-ID tie breaking.
- `bounded_exact_min_change` comparator for small instances with explicit truncation and deterministic fallback.
- Lexicographic minimization of unscheduled tasks, changed tasks, total displacement, makespan, and stable starts.
- Exact immutable-task pinning, operational-signature checks, predecessor closure, and fail-closed conflict codes.
- Revalidation of revised dependencies, windows, horizons, deadlines, capacities, and cumulative resource use.
- Explicit partial mode with structured unresolved-task diagnostics; complete mode rejects infeasible repair.
- Separate preserved, moved, added, removed, and unscheduled task outcomes.
- Canonical hashes for the previous schedule, revised request, and repaired response.
- Authenticated `POST /api/v1/preparation/schedule/repair` with structured `409` conflicts.
- Strict offline repair CLI and retained benchmark report.
- Machine-enforced advisory boundary: `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false`.
- Unit, input-order, metamorphic, exact-comparator, immutable-anchor, dependency, partial-output, API, CLI, benchmark, and contract tests.

### Remaining

- Protected structured repair-review UI comparing old and proposed schedules.
- Explicit human acceptance and a separate idempotent persistence action that creates a new draft while preserving both source hashes.
- Joint optimization, passive waiting and supervision handoffs, setup/cleanup models, large-neighborhood repair, infeasibility cores, and product-scale exact/relaxation methods.
- Representative-scale latency, optimality-gap, and failure-rate evidence.

## Persisted preparation operations

### Implemented

- Immutable reviewed calendars and structured calendar builder.
- Complete canonical occurrence document, profile map, optional source-plan pair, scheduler request/hash, deterministic response, and combined schedule hash.
- Server-derived hashes and replay before persistence and approval.
- Tamper detection for occurrence, task, profile, request, response, calendar, plan, and hashes.
- Legacy rows readable but non-approvable, with exact retry backfill.
- Schedule lifecycle with optimistic versions and append-only events.
- Source-linked schedule creation requires an exact approved plan version.
- Plan cancellation invalidates dependent draft/approved schedules.
- Protected operations and coverage workspaces.
- Structured final persistence review with exact source-plan, occurrence/hash, profile, calendar/hash, task-DAG, deterministic-output, read-only JSON, four confirmations, and explicit draft persistence.

### Remaining

- Persistence and lifecycle integration for an explicitly accepted repair candidate.
- Joint meal/preparation repair.
- Authenticated browser E2E for the complete plan-to-execution and repair-review chains.

## User-confirmed task execution

### Implemented

- Migration `20260802_0014` and append-only `preparation_task_execution_events`.
- Task IDs and planned timing derived only from the persisted deterministic response.
- Approved schedule requirement.
- States `planned`, `in_progress`, `completed`, and `skipped`; events `started`, `completed`, and `skipped`.
- Completion requires prior start; terminal tasks reject later events.
- Dependencies must be completed or skipped before a task starts.
- Completion cannot precede the confirmed start minute.
- Actual horizon minutes and planned-versus-actual deviation evidence.
- Mandatory reasons for skips and every nonzero deviation.
- Optimistic schedule-version increments with before/after versions.
- Exact idempotent retry and contradictory-key rejection.
- Viewer reads, editor/owner writes, and household isolation.
- Product HTTP completion requires every deterministic task to be completed or skipped.
- Protected `/preparation/operations/execution` workspace with progress, explicit actions, notes, deviations, and append-only history.
- Service, API, frontend, schema, and PostgreSQL race regressions.

### Compatibility boundary

The historical low-level `transition_schedule` service still permits approved-to-completed transitions for older internal callers. Product HTTP completion is guarded. Remaining internal callers must be migrated before terminality can move into the lowest authoritative transition layer without breaking compatibility.

### Non-claims

No inferred presence, background completion, appliance control, sensor observation, proof of cooking, temperature conclusion, contamination conclusion, or food-safety decision.

## Provenance and execution coverage

### Implemented

- Viewer-authorized household coverage endpoint and protected dashboard.
- Operational provenance denominators for calendars, schedule states, replay states, occurrence documents, scheduler requests, replayability, source-plan linkage, and schedule events.
- Separate task-execution denominators for:
  - execution-scope schedules;
  - currently approved execution schedules;
  - schedules with task history;
  - structurally invalid schedule/event histories;
  - deterministic task states;
  - terminal tasks and fully terminal schedules;
  - task events, nonzero deviations, skips, and skip reasons;
  - schedule-history and task-terminality ratios;
  - latest task-event timestamp.
- Malformed histories are excluded from task-state denominators and surfaced as warnings.
- Backend, frontend, OpenAPI, and TypeScript binding coverage.

### Interpretation boundary

Coverage describes stored structure and user-entered claims. It does not certify correctness, observation, execution quality, nutrition, equipment condition, temperature, contamination, or food safety.

## Frontend

### Implemented

- Protected lazy routes and profile-completion routing.
- Dashboard, planner, household/pantry, plan review, occurrence confirmation, analytics, settings, preparation editor, reviewed pipeline, structured operations review, task execution, calendar builder, combined provenance/execution coverage, and research views.
- Role-aware controls and exact provenance surfaces.
- Mechanical TypeScript binding gates for food evidence, preparation operations, and household plans.
- Vitest coverage for operations, execution, coverage, calendars, plans, household switching, authorization, and failure states.

### Remaining

- Structured repair-review and explicit acceptance UI.
- Authenticated Playwright/PostgreSQL journeys, automated axe, keyboard-only/screen-reader suites, visual regression, offline/PWA policy, and internationalization.

## Governed offline research

### Executable baselines

- TF-IDF, BM25, popularity, Bayesian popularity, content, item-kNN, matrix factorization, MMR, Bradley-Terry, LinUCB, and Thompson sampling.
- Temporal ranking metrics and hard filters.
- Moving average, seasonal naive, exponential smoothing, Holt, Croston, and TSB with rolling-origin metrics.
- Ridge, Kaplan-Meier, Mahalanobis OOD, and split conformal.
- FEFO inventory replay and forecast-to-inventory evaluation.

### Research-only or blocked

- Vision/multimodal nutrition, constrained generation, graph-neural substitution, causal/off-policy promotion, continual/federated personalization, privacy-sensitive learning, sustainability claims, autonomous procurement/appliances, and clinical personalization.

## CI and operational evidence

### Configured

- Compile, dependency, backend, repository, Alembic, catalog, OpenAPI, and frontend-binding gates.
- Planner, preparation, preparation-repair, ranking, forecasting, inventory, and closed-loop benchmarks.
- Repair contract, advisory API, CLI, immutable-anchor, metamorphic, and exact-comparator gates.
- Fresh SQLite/PostgreSQL migrations.
- Evidence import/lifecycle manifests.
- PostgreSQL inventory, idempotency, evidence, plan, preparation-operations, and task-execution probes.
- Frontend lint, Vitest, build, container build, and retained reports.

### Not yet claimed

The exact latest `main` push workflows have not been observed complete and green through the available connector. Committed tests and configured gates are not represented as executed evidence until the hosted runs and retained artifacts are inspected.

## Immediate priorities

1. Inspect and close the exact latest hosted workflows and retained artifacts.
2. Migrate remaining low-level completion callers to the task terminality guard.
3. Add authenticated Playwright/PostgreSQL and automated accessibility coverage.
4. Build protected structured repair review, explicit acceptance, and separate idempotent draft persistence.
5. Expand reviewed evidence and cross-domain coverage.
6. Add joint meal/preparation repair, larger-instance methods, infeasibility explanations, and representative-scale benchmarks.
7. Expand forecasting uncertainty, stochastic inventory costs, ranking robustness, identity lifecycle, backups, observability, SLOs, and incident evidence.

Detailed specifications:

- `docs/HOUSEHOLD_PLAN_LIFECYCLE.md`;
- `docs/PREPARATION_OPERATIONS.md`;
- `docs/PREPARATION_REPAIR.md`;
- `docs/ROADMAP.md`;
- exhaustive audit continuation documents under `docs/`.
