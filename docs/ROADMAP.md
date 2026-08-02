# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-02  
**Execution rule:** implement directly on `main` in coherent commits. Keep code, tests, migrations, contracts, fixtures, catalogs, CI, and public documentation synchronized. Do not rewrite history.

Current boundary:

- migration head `20260802_0013`;
- API `0.9.0`;
- OpenAPI contract `2026-08-02.3`;
- food-evidence bindings `2026-08-01.2`;
- preparation-operations bindings `2026-08-02.2`;
- household-plan bindings `2026-08-02.3`;
- catalog `2026-08-01.3`;
- 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

## Definition of done

A product capability requires strict contracts, authorization, persistence, migration, provenance, UX, tests, concurrency and failure handling, operational evidence, rollback, and truthful limitations. Research work requires licensed or consented data, leakage-safe evaluation, deterministic or seeded replay, calibration and subgroup analysis where relevant, artifact lineage, and explicit readiness.

A class, endpoint, fixture, or catalog row is not completion.

# Completed architecture milestones

## C1 — Transactional household platform

- Authentication and explicit profile-completion boundary.
- Owner/editor/viewer households and hashed invitations.
- Transactional pantry, leftovers, inventory events, reservations, optimistic versions, and full-request idempotency.
- PostgreSQL race probes.

## C2 — Quantity-aware meal planning

- Deterministic horizon planner with hard restrictions before optimization.
- Household target aggregation and pantry-aware objectives.
- Persisted plan documents, shopping reconciliation, reservations, and batch grouping.
- Pareto, optional CP-SAT/MILP, robust-scenario, and exact comparator paths.

## C3 — Human-reviewed household plan lifecycle

- Migration-backed optimistic `draft`, `approved`, and `cancelled` plan states.
- Owner approval and editor/owner cancellation with explicit reasons.
- Append-only plan events, exact idempotency, stale-version rejection, and PostgreSQL races.
- Protected plan-review workspace.
- Exact approved source-plan ID/version requirement for preparation schedules.
- Atomic reservation release and dependent schedule invalidation on cancellation.

## C4 — Immutable evidence platform

- Reviewed preparation profiles, conversions, storage policies, exact leftover links, hashes, source/reviewer metadata, supersession, and active uniqueness.
- Atomic import/lifecycle tools, manifests, locks, and concurrency probes.

## C5 — Deterministic preparation scheduling

- Strict task/resource/DAG contracts.
- Multi-window capacities, gap containment, deadlines, dependency propagation, utilization, critical path, and structured infeasibility.
- Bounded exact comparator and metamorphic suite.

## C6 — Persisted preparation operations

- Immutable reviewed calendars and structured calendar builder.
- Complete occurrence documents, profile maps, scheduler requests/responses, and hashes.
- Replay before persistence and approval.
- Schedule lifecycle, append-only events, coverage dashboard, and PostgreSQL races.
- Typed pipeline handoff with no automatic persistence or approval.

## C7 — Forecasting, ranking, and inventory evaluation

- Dense and intermittent-demand forecasting with rolling-origin evaluation.
- Ranking/recommendation baselines with temporal hard-filter evaluation.
- FEFO inventory replay and forecast-to-inventory closed-loop metrics.

## C8 — Release governance

- Linear Alembic validation.
- Repository, catalog, OpenAPI, and three TypeScript binding gates.
- Fresh SQLite/PostgreSQL migrations.
- Backend/frontend/container jobs and retained reports.

# P0 — Verification closure

## P0.1 Observe one exact complete workflow

- Identify the latest `main` SHA and matching Actions run.
- Inspect backend, migration, PostgreSQL, frontend, and container jobs.
- Repair every failure without weakening required gates.
- Inspect retained JSON reports and record exact commit/run identity.
- Do not claim green before observation.

## P0.2 Expand properties and state-machine tests

Add generated or metamorphic invariants for:

- parsing and exact conversions;
- inventory conservation and interval arithmetic;
- reservation and plan lifecycle state machines;
- plan cancellation versus schedule creation races;
- larger preparation DAGs and heuristic/exact parity;
- evidence supersession;
- FEFO and closed-loop inventory;
- ranking hard filters and temporal leakage;
- migration and catalog invariants.

## P0.3 TypeScript and transport strictness

- Enable stricter compiler options incrementally.
- Test nullable versus omitted fields, enum drift, empty bodies, `204`, and `205`.
- Expand generated bindings and eliminate duplicate handwritten DTOs.

# P1 — Complete approved-plan preparation workflow

## P1.1 Plan approval prerequisite — implemented

Implemented:

- exact optimistic versions;
- human approval/cancellation;
- events and idempotency;
- role controls and non-disclosure;
- source-plan approval enforcement;
- reservation release and schedule invalidation;
- frontend review workspace;
- service, API, frontend, and PostgreSQL tests.

Remaining hardening:

- authenticated Playwright/PostgreSQL journey;
- accessibility and visual regression;
- account/household export and plan retention policy.

## P1.2 Approved-plan occurrence generation — next

Build a server-authoritative candidate occurrence endpoint from an exact approved plan ID/version.

Required behavior:

- reject draft, cancelled, stale, or cross-household plans;
- derive each day/meal recipe occurrence from the immutable stored plan document;
- retain day, meal slot, recipe ID/name, planned portion multiplier, and source recipe servings;
- require the household to confirm final servings and required finish minute;
- expose missing or incompatible reviewed preparation profiles;
- allow explicit exclusion of an occurrence without mutating the plan;
- produce canonical `preparation-occurrence-set-v1` only after confirmation;
- never persist or schedule automatically.

## P1.3 Structured compile and schedule review

Replace raw bundle JSON with a structured surface showing:

- approved plan ID/version;
- occurrence document and local hash preview;
- active reviewed calendar identity/hash;
- preparation-profile ID/version/hash and duration policy;
- tasks, dependencies, demands, deadlines, and active labor;
- deterministic scheduled/unscheduled output;
- replay and provenance warnings.

Persistence remains a separate explicit action. Approval remains owner-only and server-replayed.

## P1.4 Browser E2E and accessibility

Add Playwright against PostgreSQL for:

- household generation → draft review → approval;
- occurrence confirmation;
- active calendar selection;
- compile, handoff, persistence, and approval;
- stale plan/profile/calendar failures;
- plan cancellation releasing reservations and invalidating schedules;
- coverage and event history.

Add axe, keyboard-only, screen-reader landmark, and visual-regression tests.

## P1.5 Execution checklist without autonomous control

- User-confirmed task start, complete, and skip events.
- Local reminders/timers.
- Explicit deviations and reasons.
- No inferred presence, background completion, temperature proof, or appliance control.

## P1.6 Joint minimal-change repair

- Two-stage plan then schedule repair.
- Infeasibility cuts back to meal selection.
- Small-horizon joint CP-SAT benchmark.
- Large-neighborhood repair after pantry, plan, evidence, or calendar changes.
- Human acceptance before persistence.

Metrics: plan regret, changed meals, feasibility, makespan, active labor, violations, and acceptance.

# P1 — Evidence, forecasting, inventory, and ranking

## Evidence coverage and trust

- Preparation-profile coverage by recipe and serving range.
- Conversion coverage by ingredient/unit direction.
- Storage-policy coverage by category/state.
- Review age, stale evidence, abstention, source/reviewer completeness, and exact leftover links.
- Optional detached signatures, trust roots, revocation, and signed manifests.
- More real reviewed recipes, conversions, and policies.

## Forecasting and inventory

- Last-value, drift, SBA, ADIDA, IMAPA, Theta, and optional ARIMA/ETS.
- Quantile and conformal intervals.
- Hierarchical reconciliation and shift strata.
- Variable lead times, partial delivery, cancellation, substitution, pending orders, and explicit costs.
- Service/waste/cost Pareto evaluation without automatic procurement.

## Ranking and policy safety

- Cold-start and sparse-user strata.
- Exposure/popularity bias, calibration, serendipity, and long-tail metrics.
- Propensity validation before off-policy evaluation.
- Safe-policy improvement, sequential monitoring, rollback, and kill switch before online learning.

# P2 — Security, privacy, reliability, and operations

- Verified email, reset, MFA, token rotation/revocation, and rate limiting.
- Reviewed ownership transfer and recovery.
- Account/household archive, deletion, export, and retention policy.
- Backup/restore and point-in-time recovery drills.
- Large-table migration rehearsal, pooling, failover, SLOs, tracing, incident runbooks, SBOM, scans, and attestations.

# P3 — Gated research

Remain disabled pending prerequisites:

- vision and multimodal nutrition;
- constrained recipe generation;
- graph-neural substitution;
- causal/off-policy promotion;
- continual/federated personalization;
- privacy-sensitive learning;
- sustainability claims;
- clinical personalization;
- autonomous appliance or procurement control.

Each requires licensed/consented data, leakage-safe splits, calibration, OOD/subgroup analysis, privacy review, human review, lineage, promotion approval, rollback, and monitoring.

# Immediate execution order

1. Inspect and close the exact latest hosted workflow.
2. Implement approved-plan candidate occurrence derivation and confirmation.
3. Build structured compile/schedule review.
4. Add authenticated E2E and accessibility coverage.
5. Add per-task execution/deviation events.
6. Add minimal-change joint repair.
7. Expand reviewed evidence and cross-domain coverage.
8. Continue forecasting, inventory, ranking, security, and reliability hardening.

See `docs/HOUSEHOLD_PLAN_LIFECYCLE.md` and the exhaustive audit continuation documents for exact completed scope and limitations.
