# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-02  
**Execution rule:** implement directly on `main` in coherent commits. Keep code, tests, migrations, contracts, fixtures, catalogs, CI, and public documentation synchronized. Do not rewrite history.

Current boundary:

- migration head `20260802_0014`;
- API `0.12.1`;
- OpenAPI contract `2026-08-02.6`;
- food-evidence bindings `2026-08-01.2`;
- preparation-operations bindings `2026-08-02.4`;
- household-plan bindings `2026-08-02.4`;
- catalog `2026-08-01.3`;
- 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

## Definition of done

A product capability requires strict contracts, authorization, persistence, migration, provenance, UX, tests, concurrency/failure handling, operational evidence, rollback, and truthful limitations. Research work requires licensed or consented data, leakage-safe evaluation, deterministic or seeded replay, calibration/subgroup analysis where relevant, artifact lineage, and explicit readiness.

A class, endpoint, fixture, configured workflow, or catalog row is not completion or executed evidence by itself.

# Completed architecture milestones

## C1 — Transactional household platform

Authentication, explicit profile completion, household roles, hashed invitations, transactional pantry/leftovers, reservations, optimistic versions, exact idempotency, and PostgreSQL race probes.

## C2 — Quantity-aware meal planning

Deterministic horizon planning, hard restrictions, household target aggregation, pantry-aware objectives, persisted plans, shopping reconciliation, reservations, batch grouping, Pareto, optional CP-SAT/MILP, robust scenarios, and exact comparators.

## C3 — Human-reviewed plan lifecycle

Migration-backed draft/approved/cancelled states, owner approval, editor/owner cancellation, append-only events, stale-version and contradictory-key rejection, atomic reservation release, dependent schedule invalidation, protected review, and exact approved source-plan references.

## C4 — Approved-plan occurrence confirmation

Exact approved-plan candidates, deterministic occurrence identity, serving-count semantics, descriptive batch scale, explicit inclusion/deadlines/priorities/duration policy, reviewed-profile compatibility, canonical non-persisted occurrence documents, and protected confirmation UX.

## C5 — Immutable evidence platform

Reviewed preparation profiles, conversions, storage policies, exact leftover links, hashes, source/reviewer metadata, supersession, active uniqueness, import/lifecycle manifests, locks, and concurrency probes.

## C6 — Deterministic preparation scheduling

Strict task/resource/DAG contracts, multi-window capacity, gap containment, deadlines, dependency propagation, utilization, critical path, structured infeasibility, reviewed-profile compilation, bounded exact comparison, and metamorphic tests.

## C7 — Persisted preparation operations

Immutable reviewed calendars, structured calendar builder, canonical occurrence documents, exact profile maps, scheduler requests/responses/hashes, replay before persistence/approval, schedule lifecycle, append-only events, source-plan cancellation propagation, handoff v2, and PostgreSQL races.

## C8 — User-confirmed task execution

Migration `20260802_0014`, append-only started/completed/skipped events, planned/in-progress/completed/skipped states, deterministic task identity, dependency chronology, completion-after-start, actual/deviation evidence, mandatory reasons, optimistic versions, idempotency, role controls, guarded HTTP schedule completion, protected execution workspace, and service/API/frontend/PostgreSQL tests.

Compatibility hardening remains: migrate every older internal low-level completion caller to the task-terminal guard, then enforce terminality in the lowest authoritative transition service.

## C9 — Provenance and execution coverage

- Operational provenance denominators for calendars, schedule states, occurrence documents, deterministic requests, replayability, source-plan linkage, and schedule events.
- Separate execution denominators for execution-scope schedules, active approved schedules, schedules with task history, invalid histories, deterministic task states, terminal tasks, fully terminal schedules, deviations, skips, skip reasons, and latest task-event time.
- Malformed histories excluded from task-state denominators and surfaced as warnings.
- Backend, frontend, OpenAPI, TypeScript, and household-isolation tests.
- Explicit interpretation boundary: stored structure and user-entered claims, not observation, correctness, nutrition quality, appliance state, temperature, or food safety.

## C10 — Forecasting, ranking, and inventory evaluation

Dense/intermittent-demand forecasting, rolling-origin evaluation, ranking baselines and temporal hard filters, FEFO inventory replay, and forecast-to-inventory closed-loop metrics.

## C11 — Release governance

Linear Alembic validation, repository/catalog/OpenAPI/frontend contracts, fresh SQLite/PostgreSQL migrations, backend/frontend/container jobs, retained reports, and focused task-execution concurrency workflow.

# P0 — Verification closure

## P0.1 Observe one exact complete workflow

- Identify the latest `main` SHA and matching broad/focused Actions runs.
- Inspect backend, migrations, PostgreSQL, frontend, and container jobs.
- Repair failures without weakening gates.
- Inspect retained reports and record commit/run identity.
- Make no green claim before observation.

## P0.2 Migrate low-level completion callers

- Inventory direct `transition_schedule(...COMPLETED...)` callers.
- Route product, script, fixture, and test callers through the terminality guard where execution semantics apply.
- Preserve exact lifecycle idempotency and historical readability.
- Add a repository contract rejecting new unguarded operational completion callers.
- Move terminality into the authoritative low-level transition after migration.

## P0.3 Expand properties and state machines

Add generated invariants for task transitions, dependency partial orders, identical/competing event races, plan/reservation lifecycles, inventory conservation, larger preparation DAGs, evidence supersession, FEFO/closed-loop replay, ranking leakage, and migration/catalog integrity.

## P0.4 TypeScript and transport strictness

Enable stricter compiler settings incrementally; test nullable/omitted fields, enum drift, empty bodies, `204`/`205`; expand generated bindings; eliminate duplicate DTOs; and validate lowercase SHA-256 fields.

# P1 — Complete preparation operations

## P1.1 Structured final persistence review — next product slice

Replace raw bundle JSON editing with a structured review surface showing:

- approved plan ID/version;
- occurrence document/hash;
- active reviewed calendar identity/hash;
- exact profile versions and duration policy;
- tasks, dependencies, demands, deadlines, active labor, and supervision declarations;
- deterministic scheduled/unscheduled output;
- replay/provenance warnings;
- final explicit persistence confirmation.

Canonical JSON inspection/export remains optional. Persistence and owner approval remain separate actions.

## P1.2 Browser E2E and accessibility

Playwright against PostgreSQL for generation → plan approval → occurrence confirmation → calendar selection → compile → handoff → persistence → approval → task execution → guarded completion → cancellation/invalidation → coverage/history. Add stale/tampered/adversarial paths plus axe, keyboard-only, screen-reader, and visual-regression tests.

## P1.3 Local timers/reminders without inference

Optional local assistance only. Timer expiration never writes completion or implies cooking. Explicit user confirmation remains mandatory. No presence, temperature, appliance, or food-safety inference.

## P1.4 Joint minimal-change repair

Two-stage and joint baselines, infeasibility cuts, small-horizon CP-SAT, large-neighborhood repair, preservation of completed work and historical provenance, scenario stress, and explicit human acceptance.

# P1 — Evidence, forecasting, inventory, and ranking

## Evidence coverage and trust

Preparation-profile, conversion, storage-policy, review-age, stale-evidence, abstention, source/reviewer, and exact-link denominators; optional detached signatures/trust roots/revocation; and broader reviewed evidence.

## Forecasting and inventory

Last-value, drift, SBA, ADIDA, IMAPA, Theta, optional ARIMA/ETS, quantile/conformal intervals, hierarchical reconciliation, shift strata, variable lead times, pending orders, explicit costs, and service/waste/cost Pareto analysis without autonomous procurement.

## Ranking and policy safety

Cold-start/sparse-user strata, exposure/popularity bias, calibration, serendipity, long-tail metrics, propensity validation, safe-policy improvement, monitoring, rollback, and kill switches before online learning.

# P2 — Security, privacy, reliability, and operations

Verified email, reset, MFA, token rotation/revocation, rate limiting, ownership recovery, account/household lifecycle, backup/restore, point-in-time recovery, large-table rehearsal, pooling/failover, SLOs, tracing, incidents, SBOM, scans, and attestations.

# P3 — Gated research

Vision/multimodal nutrition, constrained generation, graph-neural substitution, causal/off-policy promotion, continual/federated personalization, privacy-sensitive learning, sustainability claims, clinical personalization, and autonomous appliance/procurement control remain disabled pending licensed/consented data, leakage-safe evaluation, calibration, OOD/subgroup analysis, privacy review, human review, lineage, rollback, and monitoring.

# Immediate execution order

1. Inspect and close the exact latest hosted workflows.
2. Migrate low-level completion callers and make terminality authoritative.
3. Build structured final persistence review.
4. Add authenticated E2E and accessibility coverage.
5. Add deterministic minimal-change repair.
6. Expand reviewed evidence and cross-domain coverage.
7. Continue forecasting, inventory, ranking, security, and reliability hardening.

See `docs/HOUSEHOLD_PLAN_LIFECYCLE.md`, `docs/PREPARATION_OPERATIONS.md`, and the exhaustive audit continuation documents for exact scope and limitations.
