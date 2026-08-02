# NutriFlavorOS Implementation Status

**Status date:** 2026-08-02  
**Development policy:** coherent direct commits to `main`; no feature pull requests or development branches; no history rewriting.  
**Database migration head:** `20260802_0014`  
**API version:** `0.12.0`  
**OpenAPI release contract:** `2026-08-02.5`  
**Food-evidence frontend binding contract:** `2026-08-01.2`  
**Preparation-operations frontend binding contract:** `2026-08-02.3`  
**Household-plan frontend binding contract:** `2026-08-02.4`  
**Effective research catalog:** `2026-08-01.3`

Governed research inventory remains:

- **37 task contracts**;
- **30 dataset families**;
- **75 model or algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

A class, endpoint, committed test, synthetic fixture, or catalog row is not by itself a product-readiness, quality, clinical-validation, food-safety, execution-verification, or green-build claim.

## 1. Identity and household collaboration

### Implemented

- Argon2 password hashing and signed JWTs with issuer, audience, timing, and ID claims.
- Startup refusal for missing or weak signing secrets.
- Authenticated profile bootstrap and explicit profile-completion state.
- Owner, editor, and viewer roles with `404` non-disclosure.
- Hashed email-bound, expiring, single-use invitations.
- Invitation replacement, revocation, exact-email acceptance, retries, and race locking.
- Linked and planning-only members with serving multipliers and explicit restrictions.

### Remaining

- Verified email, password reset, MFA, token rotation/revocation, authentication rate limits, reviewed ownership transfer, household archive/delete, complete export/delete, and support tooling.

## 2. Database, migrations, and release integrity

### Implemented

- Transactional SQLite and PostgreSQL paths.
- One linear Alembic chain through `20260802_0014`.
- Runtime startup verifies the exact migration revision and required tables.
- Fresh SQLite and PostgreSQL migration jobs.
- Database constraints for inventory, roles, evidence, preparation operations, plan lifecycle, replay provenance, optimistic versions, schedule lifecycle, and task execution transitions.
- Additive ORM mappings load during backend package initialization so `Base.metadata`, API, CLI, and tests see one schema independent of service import order.
- Complete Alembic fork, orphan, and dependency validation.
- API `0.12.0` and OpenAPI contract `2026-08-02.5`.

### Remaining

- Backup/restore and point-in-time recovery drills, large-table rehearsal, retention/purge jobs, hosted pool and replica guidance, failover, and disaster-recovery evidence.

## 3. Pantry, leftovers, inventory, and reservations

### Implemented

- Versioned pantry lots with quantity intervals, units, source, expiry/open times, and metadata.
- Append-only purchase, consumption, discard, adjustment, leftover, reservation, and reservation-commit events.
- Negative-stock and incompatible-unit prevention.
- FEFO allocation and expired-stock exclusion.
- Reservation creation, release, commit, expiry, overbooking prevention, full-request fingerprints, and PostgreSQL races.
- Shopping reconciliation and batch-preparation grouping.
- Cancelling a household plan releases every active reservation for that plan in the same transaction as the plan transition.

### Remaining

- Reviewed cross-unit allocation in every path, receipt/barcode import, lot split/merge UX, recall/quarantine, offline conflict handling, variable lead time, pending orders, and bulk reconciliation.

## 4. Immutable food and preparation evidence

### Implemented

- Immutable conversion, storage-policy, and preparation-profile histories.
- Natural/version keys, source, reviewer, UTC review time, SHA-256, supersession, state, and active uniqueness.
- Exact reviewed conversion application with evidence identity and output intervals.
- Exact leftover-to-storage-policy-version links.
- Typed dry-run/apply/reapply imports, manifests, lifecycle actions, advisory locks, and concurrency probes.
- Preparation profiles with serving range, task DAG, duration interval, resource demand, active-work/supervision declarations, and immutable provenance.

### Remaining or blocked

- Broader reviewed coverage, signed documents and trust roots, production object retention, micronutrient normalization, reviewed parse workflow, time-temperature instrumentation, and sensors. Autonomous safe-to-eat decisions remain prohibited.

## 5. Meal planning and household plan lifecycle

### Implemented

- Conservative ingredient parsing, serving scaling, reviewed conversions, and hard restrictions before optimization.
- Deterministic household horizon beam search with nutrition, preference, cost, variety, repetition, pantry, and cuisine objectives.
- Household target aggregation, persisted plan documents, warnings, diagnostics, shopping reconciliation, and optional reservations.
- Pareto, optional CP-SAT/MILP, robust scenario, and exact small-instance comparator paths.
- Migration `20260802_0013` adds optimistic plan versions and `draft`, `approved`, and `cancelled` states.
- Generated household plans begin as drafts; generation is not approval.
- Owner-only exact-version approval and editor/owner cancellation with actor/time, reason, idempotency fingerprint, and append-only events.
- Identical transition retries collapse; contradictory key reuse and stale versions fail closed.
- Cancellation releases active reservations and invalidates dependent draft or approved preparation schedules atomically.
- Viewer-authorized list/get/event APIs and protected `/household/plans` review workspace.
- Approved-plan occurrence candidate and confirmation API plus protected `/household/plans/occurrences` workspace.
- Stored portions are treated as serving counts, with recipe batch scale reported separately; deadlines are entered explicitly rather than inferred from meal-slot names.

### Remaining

- Standalone immutable confirmed-occurrence records; currently the canonical document becomes durable when a schedule is persisted.
- Joint meal/preparation optimization, minimal-change repair, exact lot allocation, Pareto UX, chance/distributionally robust planning, and representative-scale benchmarks.

## 6. Deterministic preparation scheduling

### Implemented

- Strict tasks, resources, capacities, dependencies, deadlines, and provenance.
- Multi-window availability with overlap and horizon checks.
- Explicitly empty or mixed legacy/explicit calendar forms fail closed.
- Tasks must fit one continuous containing window and cannot cross unavailable gaps.
- Cumulative resource capacity, dependency propagation, utilization, peak usage, critical path, and machine-readable infeasibility.
- Reviewed-profile compile-and-schedule path.
- Bounded exact comparator and metamorphic tests for ordering, unused resources, capacity, window expansion, ambiguous calendars, and occurrence canonicalization.

### Remaining

- Joint plan/schedule optimization, passive waiting and supervision handoffs, setup/cleanup models, large-neighborhood repair, infeasibility cores, and product-scale exact or relaxation methods.

## 7. Persisted preparation operations

### Implemented

- Migrations `20260801_0009` through `20260801_0012` for calendars, schedules, requests, occurrence documents, state constraints, and append-only schedule events.
- Immutable reviewed household resource calendars.
- Structured protected calendar builder with templates, dynamic resources/windows, strict validation, operational predecessor diff, canonical import/export, review confirmations, stale-review reset, and owner activation.
- Complete canonical occurrence document, profile map, optional source-plan pair, scheduler request/hash, deterministic response, and combined schedule hash.
- Server-derived occurrence hash/version and replay before persistence and approval.
- Tamper detection for occurrence, task, profile, request, response, calendar, plan, and hashes.
- Legacy rows readable but non-approvable, with exact retry backfill.
- Schedule lifecycle with optimistic versions and append-only events.
- Provenance coverage endpoint/dashboard with explicit denominators and non-safety interpretation.
- Source-linked schedule creation requires an exact approved household-plan version.
- Plan cancellation atomically invalidates dependent draft/approved schedules and appends invalidation evidence.

### Remaining

- Structured final persistence review replacing raw expert JSON editing.
- Joint minimal-change repair.
- Authenticated browser E2E for plan approval, calendar activation, occurrence handoff, persistence, task execution, stale/tampered rejection, cancellation, supersession, coverage, and histories.

## 8. User-confirmed preparation task execution

### Implemented

- Migration `20260802_0014` creates append-only `preparation_task_execution_events`.
- Task IDs and planned timing are resolved only from the persisted deterministic schedule response.
- Execution events require an approved schedule.
- Explicit task states: `planned`, `in_progress`, `completed`, and `skipped`.
- Explicit events: `started`, `completed`, and `skipped`.
- `completed` requires a prior `started`; terminal tasks reject later events.
- Dependent tasks cannot start until every deterministic prerequisite is explicitly completed or skipped.
- Completion minute cannot precede the confirmed start minute.
- Start deviation is actual minus planned start; completion deviation is actual minus planned finish.
- Skip and every nonzero deviation require a nonblank human reason.
- Every task event increments the schedule optimistic version and captures before/after versions.
- Exact retries return the existing event; contradictory idempotency reuse fails closed.
- Viewer read and editor/owner mutation authorization with cross-household non-disclosure.
- The normal HTTP schedule-completion route requires every deterministic task to be completed or skipped.
- Protected `/preparation/operations/execution` workspace with progress, task actions, actual minutes, reasons, notes, and append-only history.
- Service, authenticated API, frontend, and PostgreSQL race regressions are committed.

### Compatibility boundary

The established low-level `transition_schedule` service still permits the historical approved-to-completed transition for older internal callers. Product HTTP completion uses the execution guard. Removing the low-level compatibility path requires a controlled migration of all internal consumers rather than silently changing a long-standing service contract.

### Deliberate non-claims

- No inferred presence or background completion.
- No appliance control or sensor observation.
- No proof that cooking occurred.
- No temperature, contamination, or food-safety conclusion.
- No timer or reminder may imply task completion.

## 9. Frontend

### Implemented

- Protected lazy routes and profile-completion routing.
- Dashboard, personal planner, household/pantry, plan review, occurrence confirmation, analytics, settings, preparation editor, reviewed pipeline, operations, task execution, calendar builder, provenance coverage, and research views.
- Role-aware mutation controls.
- Exact plan IDs/versions and evidence hashes shown where operationally relevant.
- `preparation-operations-handoff-v2` with browser provenance validation.
- Mechanical TypeScript binding gates for food evidence, preparation operations, and household plan lifecycle.
- Vitest coverage for operations, task execution, coverage, calendar review, plan review, household switching, role controls, and failure states.

### Remaining

- Structured final schedule persistence review, authenticated Playwright/PostgreSQL journeys, automated axe, keyboard-only and screen-reader suites, visual regression, offline/PWA policy, and internationalization.

## 10. Governed offline research

### Executable baselines

- TF-IDF, BM25, popularity, Bayesian popularity, content, item-kNN, matrix factorization, MMR, Bradley-Terry, LinUCB, and Thompson sampling.
- Temporal ranking metrics including accuracy, coverage, novelty, diversity, groups, and hard violations.
- Moving average, seasonal naive, exponential smoothing, Holt, Croston, and TSB with rolling-origin metrics.
- Ridge, Kaplan-Meier, Mahalanobis OOD, and split conformal baselines.
- FEFO inventory replay and forecast-to-inventory evaluation.

### Research-only or blocked

- Vision and multimodal nutrition, constrained generation, graph-neural substitution, causal/off-policy promotion, continual/federated personalization, privacy-sensitive learning, sustainability claims, autonomous procurement/appliances, and clinical personalization.

## 11. CI and operational evidence

### Configured

- Compile, dependency, backend test, repository, Alembic, catalog, OpenAPI, and frontend-binding gates.
- Planner, preparation, ranking, forecasting, inventory, and closed-loop benchmarks.
- Fresh SQLite/PostgreSQL migrations.
- Evidence import and lifecycle manifests.
- PostgreSQL inventory, request-idempotency, evidence, preparation, preparation-operations, household-plan lifecycle, and task-execution probes.
- Frontend lint, Vitest, build, container build, and retained JSON reports.

### Not yet claimed

The exact latest `main` push workflows have not been observed complete and green through the available connector in this execution context. Committed tests and configured gates are not represented as executed evidence until the hosted runs and retained artifacts are inspected.

## Immediate priorities

1. Inspect and close the exact latest hosted workflows.
2. Replace raw final schedule-bundle JSON with structured persistence review.
3. Add authenticated Playwright/PostgreSQL and automated accessibility coverage for the complete plan-to-execution chain.
4. Migrate remaining low-level schedule-completion callers to the task terminality guard.
5. Add deterministic minimal-change plan/schedule repair with explicit human acceptance.
6. Expand reviewed evidence and cross-domain coverage.
7. Expand forecasting uncertainty, stochastic inventory costs, ranking robustness, identity lifecycle, backups, observability, SLOs, and incident evidence.

Detailed records:

- `docs/EXHAUSTIVE_AUDIT_2026-08-02.md`;
- `docs/EXHAUSTIVE_AUDIT_2026-08-02_CONTINUATION.md`;
- `docs/EXHAUSTIVE_AUDIT_2026-08-02_CALENDAR_BUILDER.md`;
- `docs/EXHAUSTIVE_AUDIT_2026-08-02_PLAN_LIFECYCLE.md`;
- `docs/HOUSEHOLD_PLAN_LIFECYCLE.md`;
- `docs/PREPARATION_OPERATIONS.md`.
