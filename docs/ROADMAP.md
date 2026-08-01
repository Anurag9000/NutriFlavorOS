# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-01  
**Execution rule:** implement directly on `main` in coherent commits. Keep code,
tests, migrations, contracts, fixtures, capability registrations, catalog
records, CI, and public documents synchronized.

Current platform boundary:

- database migration head `20260801_0011`;
- API version `0.7.0`;
- OpenAPI release contract `2026-08-01.4`;
- food-evidence frontend binding contract `2026-08-01.2`;
- preparation-operations frontend binding contract `2026-08-01.1`;
- effective catalog `2026-08-01.3`;
- 37 task contracts, 30 dataset families, 75 model/algorithm families,
  29 experiment contracts, and 39 feature contracts.

A class, endpoint, fixture, or catalog entry is not done unless its scope is
explicit. Product work requires authorization, persistence, migration,
provenance, UX, tests, operational evidence, and rollback. Offline research
requires strict data contracts, leakage-safe evaluation, deterministic or
seeded replay, metrics, limitations, and truthful non-enablement.

## Definition of done

Unless explicitly research-only, completion requires:

1. strict typed contract with unknown/non-finite input rejection;
2. deterministic or seeded behavior;
3. unit, adversarial, migration, concurrency, and failure tests where relevant;
4. persistence, API, and frontend integration where relevant;
5. authorization, privacy, and abuse boundaries;
6. immutable provenance and uncertainty representation;
7. operational or benchmark acceptance criteria;
8. catalog/capability readiness that matches reality;
9. synchronized OpenAPI/frontend contracts and public documentation;
10. no fabricated fallback, silent relaxation, automatic approval, or
    unobserved-green claim.

# Completed architecture milestones

## C1 — Transactional household platform

- Secure authentication and explicit profile-completion boundary.
- Owner/editor/viewer households and hashed invitations.
- Transactional pantry, leftovers, append-only inventory events, reservations,
  optimistic versions, and full-request idempotency fingerprints.
- PostgreSQL inventory/reservation/idempotency race probes.
- Evidence-driven household React workspace.

## C2 — Quantity-aware meal planning

- Deterministic horizon beam planner and hard restriction filtering.
- Household target aggregation and pantry-aware objectives.
- Persisted plan provenance, shopping reconciliation, and batch grouping.
- Pareto, optional CP-SAT/MILP, robust scenarios, and deterministic benchmark
  gate.

## C3 — Immutable evidence platform

- Reviewed preparation profiles, conversion versions, storage-policy versions,
  exact leftover links, content hashes, source/reviewer metadata, supersession,
  and one-active-reviewed constraints.
- Atomic preparation and food-evidence importers with manifests.
- Append-only evidence rejection/deactivation with read-only product history.
- Natural-key advisory locks and PostgreSQL retry/successor/lifecycle probes.
- Exact evidence provenance in product APIs and frontend views.

## C4 — Deterministic preparation scheduling

- Strict task/resource/DAG contracts.
- Multi-window capacities, gap containment, cumulative capacity, deadlines,
  dependency propagation, utilization, critical path, and structured
  infeasibility diagnostics.
- Fail-closed reviewed-profile compile-and-schedule path.
- Bounded exact branch-and-bound comparator and canonical zero-gap gate.

## C5 — Persisted preparation operations

- Immutable reviewed household resource-calendar versions.
- Explicit capacities and multi-window availability.
- Complete request/response persistence and deterministic replay.
- Calendar, request, schedule, occurrence, profile, and optional plan provenance.
- Draft/approved/invalidated/completed/cancelled lifecycle with optimistic
  versions and append-only events.
- Approval-time replay and tamper detection.
- Legacy request-missing rows readable but non-approvable; exact retry backfill.
- Calendar supersession atomically invalidates dependent active schedules.
- Database constraints for review, approval, invalidation, and event/status
  consistency.
- Owner/editor/viewer API and protected frontend workspace.
- Dedicated OpenAPI and TypeScript binding contracts.
- PostgreSQL retries, competing transitions, and supersession/approval race
  probe.

## C6 — Forecasting and inventory evaluation

- Moving average, seasonal naive, SES, damped Holt, Croston, and TSB.
- Rolling-origin forecast evaluation.
- FEFO perishable-inventory replay and closed-loop forecast/inventory analysis.
- Separate forecast, service, stockout, and waste outcomes.
- Strict canonical fixtures and direct-main gates.

## C7 — Ranking evaluation

- Popularity, Bayesian popularity, content, item-kNN, matrix factorization, and
  MMR.
- Temporal leave-last-out, common hard-allowed candidates, and violation audit.
- Recall, HitRate, MRR, NDCG, coverage, novelty, diversity, and group metrics.

## C8 — Repository and release governance

- Mechanically verified capability registry.
- Strict canonical benchmark documents.
- Complete linear Alembic-chain validation.
- Six-scenario clean-process catalog import-order proof.
- Generated OpenAPI contract validation.
- Two generated OpenAPI-to-TypeScript binding gates.
- Fresh SQLite/PostgreSQL migrations, retained reports, frontend build/tests,
  container build, and hosted concurrency matrix configuration.

# P0 — Immediate validation closure

## P0.1 Observe and close one exact complete workflow

Tasks:

- identify the exact latest `main` SHA and corresponding Actions run;
- inspect backend, migrations, PostgreSQL probes, frontend, and container jobs;
- repair every observed failure without weakening a required gate;
- inspect retained JSON reports and verify commit identity;
- document failure triage and rerun procedure.

Acceptance:

- every required job is green on one exact commit;
- no required suite is skipped or weakened;
- status documents name the verified commit/run;
- no green claim is made before inspection.

## P0.2 Property and metamorphic expansion

Add systematic generated tests for:

- ingredient parser and exact conversions;
- inventory conservation and interval arithmetic;
- reservation/idempotency state machines;
- preparation DAGs, capacities, windows, and replay hashes;
- evidence supersession/lifecycle histories;
- heuristic/exact monotonicity and parity;
- FEFO inventory and forecast/inventory closed loop;
- ranking hard filters and temporal leakage;
- migration invariants and catalog references.

Required properties include:

- input reordering does not change deterministic output;
- increasing resource capacity cannot invalidate an already feasible schedule;
- widening a usable availability window cannot invalidate a feasible schedule;
- adding usable stock cannot increase stockout on the same demand path;
- identical idempotent retry cannot change state;
- hard exclusions only remove candidates;
- superseded evidence remains readable but inactive;
- one natural key has at most one active reviewed version;
- linked historical evidence is not rewritten;
- approval cannot succeed after request/response/hash/calendar tampering.

## P0.3 TypeScript strictness and transport edge cases

Tasks:

- incrementally enable `strict`, `noImplicitAny`, unused-symbol checks, and exact
  optional-property semantics;
- prove compatibility exports are unused before removal;
- test nullable versus omitted fields, enum drift, empty body, `204`, and `205`;
- move more API surfaces under generated binding checks;
- avoid duplicate handwritten request/response shapes.

# P1 — Preparation operations completion

## P1.1 Direct reviewed-pipeline handoff

Replace JSON copy/paste with a typed handoff from the reviewed preparation
pipeline:

- export exact calendar/resource request;
- export occurrence-set version/hash and preparation-profile version map;
- export complete scheduler request/response;
- preserve source plan ID/version;
- preview all hashes and unresolved conditions;
- explicit editor persist action;
- explicit owner approval action;
- no automatic submission or approval.

Acceptance:

- the exported bundle round-trips through the operations API without manual
  rewriting;
- replay output and hashes are shown before persistence;
- browser tests cover stale calendar, stale plan, missing profile, unresolved
  tasks, and exact success.

## P1.2 Structured resource-calendar editor

Add:

- resource templates for person, burner, oven, counter, refrigerator, and custom
  equipment;
- structured multi-window editing with overlap/horizon validation;
- timezone-aware review display;
- calendar diff against predecessor;
- explicit review checklist and activation confirmation;
- import/export of canonical calendar JSON;
- accessibility and keyboard testing.

## P1.3 Plan-to-occurrence generation

- Derive candidate occurrences from an approved persisted plan version.
- Require reviewed serving count and desired finish-time confirmation.
- Surface recipes without reviewed preparation profiles.
- Show profile ID/version/hash and duration assumptions.
- Persist a confirmed immutable occurrence set and hash.
- Never auto-submit generated occurrences.
- Invalidate or regenerate candidates when plan/profile/calendar versions change.

## P1.4 Execution checklist without autonomous control

- User-confirmed task start/complete/skip events.
- Optional reminders and local timers.
- Explicit deviations and reasons.
- No inferred presence, background task completion, or appliance control.
- Do not use execution confirmation as proof of temperature or food safety.

## P1.5 Joint meal and preparation repair

Research and product pathway:

- two-stage plan then schedule repair;
- infeasibility cuts back to meal selection;
- small-horizon joint CP-SAT benchmark;
- minimal-change repair after pantry, evidence, plan, or calendar updates;
- explicit human acceptance.

Metrics:

- plan regret;
- changed-meal count;
- preparation feasibility;
- makespan and active labor;
- hard violation count;
- user-confirmed repair acceptance.

# P1 — Evidence coverage and trust

## P1.6 Evidence coverage dashboard

Metrics with explicit denominators and timestamps:

- preparation-profile coverage by recipe and serving range;
- conversion coverage by ingredient/unit direction;
- storage-policy coverage by category/state;
- review age, stale evidence, and automatic-operation abstention;
- draft, legacy, inactive, rejected, and superseded records;
- leftovers linked to exact versions;
- lifecycle activity by action, reason, actor, and age;
- calendars/schedules with complete replay provenance.

Coverage must never imply correctness or safety.

## P1.7 Signed evidence and operations documents

- Optional detached signatures for evidence import/lifecycle and calendar review
  documents.
- Signer identity, trust roots, revocation, and explicit unsigned-development
  mode.
- Verification before preflight.
- Signed manifest retention.
- Clear distinction between integrity hashing and publisher authentication.

## P1.8 Broader reviewed evidence

- Real-recipe preparation profiles and serving ranges.
- More exact densities, portion weights, package conversions, and storage
  policies.
- Reviewed parse workflow and coverage dashboard.
- Cooling/time-temperature instrumentation only through explicit validated
  integrations.
- No autonomous safe-to-eat decision.

# P1 — Forecasting, inventory, and ranking expansion

## P1.9 Forecast baselines and uncertainty

- Last-value, drift, SBA, ADIDA, IMAPA, Theta, optional ARIMA/ETS.
- Quantile regression and split-conformal forecast intervals.
- Hierarchical reconciliation.
- History-length, intermittent-demand, horizon, and distribution-shift strata.
- Interval coverage/width and subgroup reporting.
- Deep temporal models only after sufficient representative data.

## P1.10 Stochastic inventory costs

- Pending-order and pipeline metrics.
- Variable lead times, partial delivery, cancellation, and substitution.
- Purchase, holding, ordering, stockout, and waste costs.
- Scenario replay and service/waste/cost Pareto fronts.
- No automatic procurement policy selection.

## P1.11 Ranking robustness and policy safety

- Cold-start and sparse-user strata.
- Popularity and exposure bias analysis.
- Calibration, serendipity, and long-tail metrics.
- Logged-policy propensity requirements before off-policy evaluation.
- Safe policy-improvement and kill-switch requirements before any online
  learning experiment.

# P2 — Security, privacy, reliability, and accessibility

## P2.1 Authenticated browser E2E and accessibility

- Playwright journeys against PostgreSQL for signup/login/profile, household
  invitation, pantry/reservations, immutable leftover provenance, reviewed
  pipeline, calendar registration, schedule persistence/approval/invalidation,
  and event history.
- Axe audits for all protected routes and high-risk dialogs.
- Keyboard-only and screen-reader landmark tests.
- Visual regression for provenance and warning states.

## P2.2 Identity and account lifecycle

- Verified email, reset, MFA, token rotation/revocation, rate limiting.
- Reviewed ownership transfer and recovery.
- Account/household archive and deletion with provenance retention policy.
- Complete export/delete lifecycle and support tooling.

## P2.3 Hosted reliability

- Backup/restore and point-in-time recovery drills.
- Large-table migration rehearsal.
- Retention/purge policy.
- Pool sizing, read replica, and failover guidance.
- SLOs, tracing, structured audit export, and incident runbooks.

# P3 — Gated research programs

Remain disabled until their declared prerequisites are met:

- computer vision and multimodal nutrition;
- constrained recipe generation;
- graph-neural substitution;
- continual/federated personalization;
- causal analysis;
- privacy attacks and defenses;
- sustainability claims;
- clinical-condition or medication personalization;
- autonomous appliance or procurement control.

Each program requires licensed/consented data, leakage-safe splits, calibration,
OOD/subgroup evaluation, privacy review, human review, artifact lineage,
promotion approval, rollback, and monitoring before readiness can advance.

# Immediate execution order

1. Inspect and close the exact latest `main` Actions run.
2. Fix all concrete backend/frontend/migration/concurrency/container failures.
3. Add direct reviewed-pipeline-to-operations handoff.
4. Add structured calendar editing and occurrence-set generation.
5. Add authenticated Playwright/PostgreSQL and axe coverage.
6. Expand real reviewed evidence and coverage reporting.
7. Begin joint plan/schedule repair only after the operational workflow is
   verified end to end.
