# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-02  
**Execution rule:** implement directly on `main` in coherent commits. Keep code, tests, migrations, contracts, fixtures, catalogs, CI, and public documentation synchronized. Do not rewrite history.

Current boundary:

- migration head `20260802_0014`;
- API `0.12.0`;
- OpenAPI contract `2026-08-02.5`;
- food-evidence bindings `2026-08-01.2`;
- preparation-operations bindings `2026-08-02.3`;
- household-plan bindings `2026-08-02.4`;
- catalog `2026-08-01.3`;
- 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

## Definition of done

A product capability requires strict contracts, authorization, persistence, migration, provenance, UX, tests, concurrency and failure handling, operational evidence, rollback, and truthful limitations. Research work requires licensed or consented data, leakage-safe evaluation, deterministic or seeded replay, calibration and subgroup analysis where relevant, artifact lineage, and explicit readiness.

A class, endpoint, fixture, configured workflow, or catalog row is not completion or executed evidence by itself.

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

## C4 — Approved-plan occurrence confirmation

- Candidate derivation from an exact approved plan/version.
- Deterministic occurrence identity from plan day and exact meal-slot text.
- Stored serving counts and separate descriptive recipe batch scale.
- Explicit include/exclude, confirmed servings, finish minute, priority, and duration policy.
- Active reviewed preparation-profile compatibility checks.
- Canonical non-persisted occurrence document and exact profile map.
- Protected occurrence-confirmation workspace with no automatic persistence.

## C5 — Immutable evidence platform

- Reviewed preparation profiles, conversions, storage policies, exact leftover links, hashes, source/reviewer metadata, supersession, and active uniqueness.
- Atomic import/lifecycle tools, manifests, locks, and concurrency probes.

## C6 — Deterministic preparation scheduling

- Strict task/resource/DAG contracts.
- Multi-window capacities, gap containment, deadlines, dependency propagation, utilization, critical path, and structured infeasibility.
- Bounded exact comparator and metamorphic suite.

## C7 — Persisted preparation operations

- Immutable reviewed calendars and structured calendar builder.
- Complete occurrence documents, profile maps, scheduler requests/responses, and hashes.
- Replay before persistence and approval.
- Schedule lifecycle, append-only events, coverage dashboard, and PostgreSQL races.
- Typed pipeline handoff with no automatic persistence or approval.

## C8 — User-confirmed preparation task execution

- Migration `20260802_0014` and append-only task execution events.
- States `planned`, `in_progress`, `completed`, and `skipped`.
- Explicit `started`, `completed`, and `skipped` transitions.
- Task identity and planned timing derived only from the persisted deterministic response.
- Dependency chronology and completion-after-start enforcement.
- Horizon-relative actual minutes and planned-versus-actual deviations.
- Mandatory reasons for skips and nonzero deviations.
- Optimistic schedule-version increments and exact idempotency.
- Viewer read and editor/owner mutation authorization.
- Guarded HTTP schedule completion after every task is completed or skipped.
- Protected execution workspace, service/API/frontend tests, and PostgreSQL race probe.

Compatibility hardening still required: migrate all remaining internal callers away from the historical low-level unguarded completion transition, then make the terminality invariant authoritative at the lowest service layer.

## C9 — Forecasting, ranking, and inventory evaluation

- Dense and intermittent-demand forecasting with rolling-origin evaluation.
- Ranking/recommendation baselines with temporal hard-filter evaluation.
- FEFO inventory replay and forecast-to-inventory closed-loop metrics.

## C10 — Release governance

- Linear Alembic validation.
- Repository, catalog, OpenAPI, and TypeScript binding gates.
- Fresh SQLite/PostgreSQL migrations.
- Backend/frontend/container jobs and retained reports.
- Focused PostgreSQL task-execution workflow.

# P0 — Verification closure

## P0.1 Observe one exact complete workflow

- Identify the latest `main` SHA and matching broad and focused Actions runs.
- Inspect backend, migration, PostgreSQL, frontend, and container jobs.
- Repair every failure without weakening required gates.
- Inspect retained JSON reports and record exact commit/run identity.
- Do not claim green before observation.

## P0.2 Migrate low-level completion callers

- Inventory every direct `transition_schedule(...COMPLETED...)` caller.
- Route product, script, fixture, and test callers through the task-terminality guard where execution semantics apply.
- Preserve exact lifecycle idempotency.
- Move terminality validation into the authoritative low-level transition only after compatibility callers are migrated.
- Add a repository contract that rejects new unguarded completion callers.

Acceptance:

- no product or operational caller can complete a schedule without terminal task evidence;
- exact retry still returns the original completed schedule;
- legacy records remain readable;
- no silent event fabrication or backfill.

## P0.3 Expand properties and state-machine tests

Add generated or metamorphic invariants for:

- task execution transition sequences and terminality;
- dependency partial orders;
- identical and competing task-event races;
- parsing and exact conversions;
- inventory conservation and interval arithmetic;
- reservation and plan lifecycle state machines;
- plan cancellation versus schedule creation races;
- larger preparation DAGs and heuristic/exact parity;
- evidence supersession;
- FEFO and closed-loop inventory;
- ranking hard filters and temporal leakage;
- migration and catalog invariants.

## P0.4 TypeScript and transport strictness

- Enable stricter compiler options incrementally.
- Test nullable versus omitted fields, enum drift, empty bodies, `204`, and `205`.
- Expand generated bindings and eliminate duplicate handwritten DTOs.
- Add lowercase SHA-256 field checks across operational APIs.

# P1 — Complete preparation operations product

## P1.1 Structured final persistence review — next product slice

Replace raw bundle JSON editing with a structured review surface showing:

- approved plan ID/version;
- occurrence document and canonical hash;
- active reviewed calendar identity/hash;
- preparation-profile ID/version/hash and duration policy;
- tasks, dependencies, demands, deadlines, and active labor;
- deterministic scheduled/unscheduled output;
- replay and provenance warnings;
- final human persistence confirmation.

Canonical JSON inspection/export remains optional. Persistence remains a separate explicit action. Approval remains owner-only and server-replayed.

## P1.2 Task execution coverage denominators

Extend the preparation coverage API and dashboard with explicit, non-safety denominators:

- approved schedules eligible for execution;
- schedules with at least one task event;
- total deterministic tasks;
- planned, in-progress, completed, and skipped task counts;
- fully terminal approved schedules;
- task events with nonzero deviation;
- skipped tasks with reasons;
- latest task-event timestamp.

Do not collapse schedule replay provenance and task execution evidence into one misleading completeness score.

## P1.3 Browser E2E and accessibility

Add Playwright against PostgreSQL for:

- household generation → draft review → approval;
- occurrence confirmation;
- active calendar selection;
- compile, handoff, persistence, and approval;
- task start, completion, skip, deviation, and guarded final completion;
- stale plan/profile/calendar failures;
- plan cancellation releasing reservations and invalidating schedules;
- coverage and event histories.

Add axe, keyboard-only, screen-reader landmark, and visual-regression tests.

## P1.4 Local timers and reminders without execution inference

- Optional local-only timer/reminder assistance.
- Explicit user confirmation remains required for every event.
- Timer expiration must not write `completed` or imply cooking occurred.
- No background presence, temperature, appliance, or food-safety inference.
- Clear pause/reset and notification-permission UX.

## P1.5 Joint minimal-change repair

- Two-stage plan then schedule repair.
- Infeasibility cuts back to meal selection.
- Small-horizon joint CP-SAT benchmark.
- Large-neighborhood repair after pantry, plan, evidence, calendar, or execution changes.
- Preserve completed work and historical provenance.
- Human acceptance before persistence.

Metrics: plan regret, changed meals, changed tasks, feasibility, makespan, active labor, violations, and acceptance.

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

1. Inspect and close the exact latest hosted workflows.
2. Migrate remaining low-level schedule-completion callers to the terminality guard.
3. Build structured final persistence review.
4. Add task-execution coverage denominators.
5. Add authenticated E2E and accessibility coverage.
6. Add deterministic minimal-change joint repair.
7. Expand reviewed evidence and cross-domain coverage.
8. Continue forecasting, inventory, ranking, security, and reliability hardening.

See `docs/HOUSEHOLD_PLAN_LIFECYCLE.md`, `docs/PREPARATION_OPERATIONS.md`, and the exhaustive audit continuation documents for exact completed scope and limitations.
