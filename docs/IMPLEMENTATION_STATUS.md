# NutriFlavorOS Implementation Status

**Status date:** 2026-08-02  
**Development policy:** coherent direct commits to `main`; no feature pull requests or development branches; no history rewriting.  
**Database migration head:** `20260801_0012`  
**API version:** `0.8.0`  
**OpenAPI release contract:** `2026-08-02.2`  
**Food-evidence frontend binding contract:** `2026-08-01.2`  
**Preparation-operations frontend binding contract:** `2026-08-02.2`  
**Effective research catalog:** `2026-08-01.3`

Current governed inventory remains:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

An importable class, committed test, synthetic fixture, endpoint, model name, or catalog row is not by itself a product-readiness, model-quality, clinical-validation, food-safety, or production-execution claim.

## Status vocabulary

| Status | Meaning |
|---|---|
| Implemented | Typed, wired through its declared path, persisted where required, and covered by committed regression tests. |
| Executable offline baseline | Callable comparator or evaluator; not automatically selected or runtime enabled. |
| Adapter available | Guarded integration exists; acquisition, review, and enablement remain explicit. |
| Partial | Substantial code exists but a declared integration, validation, UX, or operational gate remains. |
| Research only | Architecture/experiment contract without complete data, training, evaluation, artifact, or promotion gates. |
| Blocked by data | Licensed, consented, representative, or provenance-bearing data is insufficient. |
| Blocked by validation | Calibration, OOD, subgroup, external-validation, human-review, or monitoring gates are incomplete. |
| Clinical risk | Must remain disabled without formal clinical governance and external validation. |

## 1. Identity, authentication, and profiles

### Implemented

- Argon2 password hashing and signed JWTs with issuer, audience, timing, and ID claims.
- Weak/missing signing-key refusal.
- Authenticated `/auth/me` bootstrap and self-only resources.
- Explicit profile-completion and missing-field state.
- Signup never fabricates physiology or nutrition targets.
- Planning refuses incomplete profiles.
- Shared authenticated frontend transport with structured errors and `401` invalidation.

### Remaining

- Verified email, password reset, MFA, token rotation/revocation, authentication rate limits, administrative support tooling, ownership transfer, and complete export/delete flows.

## 2. Database, migrations, and release integrity

### Implemented

- Transactional SQLAlchemy persistence with SQLite local and PostgreSQL hosted paths.
- One validated linear Alembic chain through `20260801_0012`.
- Runtime startup requires the exact recorded migration head and required tables; ORM-only schemas are rejected.
- Fresh SQLite and PostgreSQL migration jobs.
- Upgrade/downgrade regressions for immutable evidence, lifecycle, preparation operations, occurrence provenance, and state constraints.
- Database constraints for quantity/version bounds, roles/status, evidence hashes, natural keys, active-reviewed uniqueness, replay provenance pairs, source-plan pairs, calendar review state, schedule lifecycle state, and event/action pairs.
- Complete Alembic fork/orphan/dependency validation.

### Remaining

- Backup/restore drills, point-in-time recovery, large-table rehearsal, retention/purge jobs, hosted pool/read-replica guidance, and disaster-recovery evidence.

## 3. Household collaboration

### Implemented

- Owner/editor/viewer roles and `404` non-disclosure.
- Hashed email-bound, expiring, single-use invitation tokens.
- Replacement, revocation, exact-email acceptance, retry-safe acceptance, and locking for invitation/membership races.
- Linked and planning-only members with active state, serving multiplier, restrictions, allergies, dislikes, and optional targets.

### Remaining

- Reviewed ownership transfer, household archive/deletion, invitation delivery, and user-facing audit export/filtering.

## 4. Pantry, leftovers, inventory ledger, and reservations

### Implemented

- Versioned pantry lots with quantity intervals, units, source, expiry/open timestamps, and metadata.
- Append-only purchase, consumption, discard, adjustment, leftover, reservation, and reservation-commit events.
- Negative-stock and incompatible-unit prevention.
- FEFO allocation, expired-stock exclusion, reservation lifecycle, and overbooking prevention.
- Full request fingerprints in the mutation transaction and fail-closed contradictory idempotency reuse.
- PostgreSQL probes for retries, stale versions, reservations, duplicate create, and duplicate commit.
- Shopping reconciliation and batch-preparation grouping.

### Remaining

- Reviewed cross-unit allocation in every path, receipt/barcode import, lot split/merge UX, recall/quarantine, offline conflict handling, variable lead time, pending orders, and bulk reconciliation reports.

## 5. Immutable food evidence

### Implemented

- Immutable conversion, storage-policy, and preparation-profile version histories.
- Exact natural/version keys, source provenance, reviewer, UTC review time, content hash, supersession, evidence status, and active state.
- One active reviewed version per exact natural key.
- Idempotent identical retry, contradictory same-version rejection, and advisory locking.
- Exact reviewed conversion application returns evidence identity and output interval.
- New leftovers bind one exact active reviewed storage-policy version; historical provenance remains readable after withdrawal.
- Typed import and lifecycle documents, dry-run, atomic apply, idempotent reapply, manifests, append-only deactivation/rejection, and concurrency probes.

### Remaining or blocked

- Broader reviewed coverage, signed documents/trust policy, production object retention, micronutrient normalization, time-temperature instrumentation, and sensors. Autonomous “safe to eat” decisions remain prohibited.

## 6. Ingredients, recipes, and meal planning

### Implemented

- Conservative parsing with raw text, canonical name, quantity interval, unit, and parse state.
- Serving-scaled shopping aggregation and exact reviewed conversions.
- Deterministic horizon beam search with hard restrictions before optimization.
- Calories, macros, taste, cost, cuisine, variety, repeat, and pantry objectives.
- Household targets from complete linked profiles or explicit overrides.
- Persisted plans, portions, warnings, diagnostics, and optional reservations.
- Pareto, optional CP-SAT/MILP, scenario-stress, and robust-enumeration offline comparators.

### Partial or remaining

- Approved-plan occurrence generation, joint meal/resource scheduling, schedule-driven minimal-change repair, distributionally robust/chance-constrained planning, exact lot allocation, Pareto UX, reviewed parse workflow, and representative-scale benchmarks.

## 7. Preparation evidence and deterministic scheduling

### Implemented

- Immutable reviewed preparation profiles with serving range, task DAG, duration interval, resource demand, activity/supervision declarations, source, reviewer, content hash, supersession, and active state.
- Strict resources with capacity and one or more non-overlapping explicit windows, plus a preserved legacy single-window replay form.
- Explicitly empty windows and mixed legacy/explicit representations fail closed.
- Strict tasks with duration, earliest start, deadline, priority, demands, dependencies, and metadata.
- Duplicate, unknown, self, cyclic, non-finite, and extra-field rejection.
- Deterministic dependency-aware scheduling with cumulative capacity and continuous containing-window enforcement; tasks cannot bridge unavailable gaps.
- Structured missing-resource, capacity, availability, dependency, and deadline diagnostics.
- Makespan, utilization, peak use, critical-path, and search diagnostics.
- Reviewed-profile compile-and-schedule endpoint with explicit partial opt-in.
- Bounded exact comparator using the same semantics and canonical parity gate.
- Metamorphic tests for input ordering, unused resources, capacity monotonicity, availability expansion, ambiguous calendars, and occurrence-document canonicalization.

### Remaining

- Joint plan/schedule optimization, explicit passive-waiting and supervision handoffs, setup/cleanup models, large-neighborhood repair, infeasibility cores, and product-scale exact/relaxation methods.

## 8. Persisted preparation operations

### Implemented

- Migrations `20260801_0009` through `20260801_0012` cover resource calendars, schedules, append-only events, replay request/hash, lifecycle constraints, and complete occurrence-set payload persistence.
- Immutable reviewed household calendars with capacities, multi-window availability, canonical UTC review data, content hash, request fingerprint, supersession, and one active reviewed version.
- Calendar activation atomically invalidates predecessor-linked draft and approved schedules.
- Schedule creation requires the complete canonical occurrence document; version and SHA-256 are derived server-side.
- Persisted occurrence document/hash/version, profile versions, optional source-plan ID/version, calendar hash, scheduler request/hash, deterministic response, and combined schedule hash.
- Exact calendar/resource/household/plan/provenance checks.
- Server replay before persistence and again before approval.
- Tampered request, response, occurrence document, profile mapping, calendar, plan, or combined hash fails closed.
- Legacy rows remain readable but non-approvable; an exact idempotent retry may backfill missing occurrence/request provenance.
- Draft, approved, invalidated, completed, and cancelled lifecycle with optimistic versions and append-only events.
- Household-scoped provenance coverage endpoint with explicit calendar, occurrence-document, scheduler-request, replayable-schedule, source-plan-link, status, and event denominators.
- Coverage warnings identify legacy replay gaps and missing active reviewed calendars without treating coverage as correctness or safety.
- Role-aware API and frontend workspace.
- One authoritative mutation implementation; the former integrity service is a compatibility facade rather than a second write path.
- PostgreSQL probe covers identical retries, competing transitions, and calendar-supersession/approval races.

### Remaining

- Structured resource-calendar editor and predecessor diff.
- Approved-plan-to-confirmed-occurrence workflow.
- Per-task execution events, timers/reminders, skip/deviation reasons, and checklist UX.
- Joint plan/calendar optimization and minimal-change schedule repair.
- Browser E2E for stale/tampered/superseded paths.

## 9. Frontend

### Implemented

- One routed React/TypeScript application with protected lazy routes and profile-completion routing.
- Dashboard, planner, analytics, settings, household/pantry, preparation editor, reviewed pipeline, preparation operations, provenance coverage, and research views.
- Role-based mutation controls and exact evidence provenance surfaces.
- Mechanical OpenAPI-to-TypeScript checks for food evidence and preparation operations.
- `preparation-operations-handoff-v2`: complete occurrence document, source-plan pair, profile versions, request, response, and local hash preview.
- Browser-side task/occurrence/profile/duration consistency validation before handoff storage.
- Operations workspace blocks approval when occurrence or replay provenance is missing.
- Protected provenance dashboard reports exact rates and lifecycle counts, preserves household isolation, exposes gaps, and explicitly rejects safety interpretation.
- Vitest browser-environment coverage, skip link, labels, keyboard navigation, progress semantics, and reduced-motion handling.

### Remaining

- Structured non-JSON editors, authenticated Playwright/PostgreSQL end-to-end coverage, automated axe audits, screen-reader/visual regression, offline/PWA policy, and internationalization.

## 10. Governed offline research

### Executable baselines and protocols

- TF-IDF, BM25, popularity, Bayesian popularity, content ranking, item-kNN, matrix factorization, MMR, Bradley-Terry, LinUCB, and Thompson sampling.
- Temporal ranking with hard candidate filtering and Recall/HitRate/MRR/NDCG, coverage, novelty, diversity, group, and violation metrics.
- Moving average, seasonal naive, exponential smoothing, Holt, Croston, and TSB with rolling-origin MAE/RMSE/sMAPE/MASE.
- Ridge, Kaplan-Meier, Mahalanobis OOD, and split-conformal baselines.
- FEFO inventory replay and forecast-to-inventory evaluation with separate forecast/service/waste leaders.
- Strict benchmark documents, adversarial contract tests, and isolated catalog import-order verification.

### Research-only or blocked

- Vision and multimodal nutrition, constrained generation, graph-neural substitution, causal/off-policy promotion, continual/federated personalization, privacy-sensitive learning, sustainability claims, autonomous procurement/appliances, and clinical personalization.

## 11. CI and operational evidence

### Implemented configuration

- Python compileall, dependency consistency, backend tests, repository/Alembic/catalog/OpenAPI/frontend-binding gates.
- Planner, preparation, ranking, forecasting, inventory, and closed-loop benchmark gates.
- Fresh SQLite/PostgreSQL migrations.
- Evidence dry-run/apply/reapply and lifecycle manifests.
- PostgreSQL inventory, idempotency, preparation evidence, immutable evidence, lifecycle, and preparation-operations concurrency probes.
- Frontend lint, Vitest, Vite build, container build, and retained JSON validation reports.
- Workflow action references corrected to supported majors and PostgreSQL uses a run-specific credential.

### Not yet claimed

The exact latest direct-`main` hosted workflow has not yet been observed complete and green in this execution context. Committed tests and configured gates are not represented as executed evidence until that run and its retained reports are inspected.

## Immediate priorities

1. Inspect and close the exact latest GitHub Actions run.
2. Add authenticated Playwright/PostgreSQL journeys and accessibility audits.
3. Replace JSON calendar/schedule editing with structured accessible flows.
4. Generate confirmed occurrences from approved plan versions.
5. Add per-task execution/deviation events and minimal-change repair.
6. Expand reviewed preparation, conversion, and storage evidence.
7. Expand forecasting uncertainty/inventory costs and ranking cold-start/calibration/policy-safety evaluation.
8. Add backup/restore, retention, observability, SLO, and incident evidence.

See `docs/EXHAUSTIVE_AUDIT_2026-08-02.md` for the reconstructed mission, pull-request audit, detailed remaining matrix, additional research/architecture proposals, and prioritized execution plan.
