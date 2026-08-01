# NutriFlavorOS Implementation Status

**Status date:** 2026-08-01  
**Development policy:** coherent direct commits to `main`; no feature pull
requests or automated dependency-update branches.  
**Database migration head:** `20260801_0011`  
**API version:** `0.7.0`  
**OpenAPI release contract:** `2026-08-01.4`  
**Food-evidence frontend binding contract:** `2026-08-01.2`  
**Preparation-operations frontend binding contract:** `2026-08-01.1`  
**Effective research catalog:** `2026-08-01.3`

Current governed inventory:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

An importable class, committed test, synthetic fixture, endpoint, or catalog
entry is not by itself a product-readiness, model-quality, clinical-validation,
or safety claim.

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

- Argon2 password hashing and signed JWTs with issuer, audience, timing, and ID
  claims.
- Weak/missing signing-key refusal.
- Authenticated `/auth/me` bootstrap and self-only resources.
- Explicit profile-completion and missing-field state.
- Signup never fabricates physiology or nutrition targets.
- Planning refuses incomplete profiles.
- Shared authenticated frontend transport with structured errors and `401`
  invalidation.

### Remaining

- Verified email, password reset, MFA, token rotation/revocation, authentication
  rate limits, administrative support tooling, and complete export/delete flows.

## 2. Database, migrations, and release integrity

### Implemented

- Transactional SQLAlchemy persistence with SQLite local and PostgreSQL hosted
  paths.
- One validated linear Alembic chain through `20260801_0011`.
- Runtime startup requires the exact recorded migration head and all required
  tables; ORM-only schemas are rejected.
- Fresh SQLite and PostgreSQL migration jobs.
- Dedicated upgrade/downgrade regressions for immutable evidence, evidence
  lifecycle, preparation operations, replay provenance, and lifecycle state
  constraints.
- Database constraints for quantity/version bounds, role/status enums, evidence
  hashes, natural keys, active-reviewed uniqueness, exact lifecycle targets,
  replay provenance pairs, source-plan version pairs, calendar review state,
  schedule approval/invalidation state, and event/action status pairs.
- Complete Alembic fork/orphan/dependency validation.

### Remaining

- Backup/restore drills, point-in-time recovery, large-table rehearsal,
  retention/purge jobs, and hosted pool/read-replica guidance.

## 3. Household access and collaboration

### Implemented

- Owner/editor/viewer roles and `404` non-disclosure.
- Hashed email-bound, expiring, single-use invitation tokens.
- Replacement, revocation, exact-email acceptance, and retry-safe acceptance.
- Household locking for membership/invitation races.
- Invitation-required linked accounts.
- Owner escalation and ownership transfer blocked from ordinary updates.
- Linked and planning-only members with active state, serving multiplier,
  restrictions, allergies, dislikes, and optional targets.

### Remaining

- Reviewed ownership transfer, household archive/deletion, invitation delivery,
  and user-facing audit export/filtering.

## 4. Pantry, leftovers, inventory ledger, and reservations

### Implemented

- Versioned pantry lots with quantity intervals, units, source, expiry/open
  timestamps, and metadata.
- Append-only purchase, consumption, discard, adjustment, leftover,
  reservation, and reservation-commit events.
- Negative-stock and incompatible-unit prevention.
- FEFO allocation and expired-stock exclusion.
- Active/released/consumed/expired reservations and cross-plan overbooking
  prevention.
- Full request fingerprints written in the mutation transaction.
- Contradictory idempotency reuse and ambiguous legacy keys fail closed.
- PostgreSQL probes for retries, stale versions, reservations, duplicate create,
  and duplicate commit.
- Shopping reconciliation and batch-preparation grouping.

### Remaining

- Reviewed cross-unit allocation in every inventory path, receipt/barcode import,
  lot split/merge UX, recall/quarantine state, offline conflict handling, and
  bulk reconciliation reports.

## 5. Immutable conversion, storage-policy, and leftover evidence

### Implemented

- Immutable conversion and storage-policy version histories.
- Exact natural/version keys, source provenance, reviewer, UTC review time,
  content hash, supersession link, evidence status, and active state.
- One active reviewed version per exact natural key.
- Idempotent identical retry; contradictory same-version content fails.
- Advisory locking for first-version and successor races.
- Conservative legacy migration.
- Exact reviewed conversion application returns the evidence ID/version/hash,
  reviewer, source, and output interval.
- New leftovers use one exact active reviewed policy version; storage state and
  expiry bounds are checked against that record.
- Leftover event and immutable link retain exact policy ID/version/hash.
- Historical policy provenance remains readable after withdrawal.
- Frontend shows exact policy source, reviewer, scope, hash, version, and active
  or withdrawn state.

### Remaining or blocked

- Broader reviewed conversion/policy coverage, cooling/time-temperature
  instrumentation, sensor integration, and provenance-aware micronutrient
  normalization. Autonomous “safe to eat” decisions remain prohibited.

## 6. Manifest-driven evidence import and lifecycle

### Implemented

- Typed `food-evidence-import-v1` and `evidence-lifecycle-v1` documents.
- Lock-free dry-run preflight.
- Deterministic apply locks and atomic multi-family transactions.
- Idempotent reapplication, contradictory reuse rejection, exact supersession,
  source-file hashes, operator/reviewer identities, and durable pre/post
  manifests.
- Append-only deactivated/rejected events with exact target, actor, reason,
  metadata, prior active state, idempotency key, and request fingerprint.
- Reactivation prohibited; correction requires a new immutable successor.
- Authenticated lifecycle history is read-only.
- PostgreSQL retry/conflict/withdrawal-successor probes.
- Research frontend displays conversion, policy, and lifecycle histories.

### Remaining

- Optional signed documents, signer trust policy, production object-store
  retention, and external operator access controls.

## 7. Ingredients, recipes, and meal planning

### Implemented

- Conservative ingredient parsing with raw text, canonical name, intervals,
  units, and parse state.
- Serving-scaled shopping aggregation.
- Compatible-dimension conversion only; missing exact reviewed conversion fails.
- Recipe provenance and invalid-contract skipping.
- Deterministic horizon beam search with hard restrictions before optimization.
- Calories, macros, taste, cost, cuisine, variety, repeat, and pantry objectives.
- Household targets from complete linked profiles or explicit overrides.
- Persisted plan schema, portions, warnings, diagnostics, and optional
  reservations.
- Pareto, optional CP-SAT/MILP, scenario stress, and robust enumeration as
  offline comparators.

### Partial or remaining

- Joint meal/resource optimization, schedule-driven plan repair,
  distributionally robust/chance-constrained planning, exact lot allocation,
  Pareto UX, reviewed parse workflow, and representative-scale benchmarks.

## 8. Preparation evidence and deterministic scheduling

### Implemented

- Immutable reviewed preparation profiles with serving range, task DAG,
  duration interval, resource demand, activity/supervision declarations,
  source, reviewer, UTC review time, content hash, supersession, and active
  state.
- Atomic preparation-profile imports and PostgreSQL retry/successor probes.
- Strict resources with capacity and one or more non-overlapping availability
  windows.
- Strict tasks with duration, earliest start, deadline, priority, demands,
  dependencies, and metadata.
- Duplicate/unknown/self/cyclic validation and finite/extra-field rejection.
- Deterministic dependency-aware heuristic with cumulative capacity and
  common-containing-window enforcement.
- Tasks cannot span unavailable gaps.
- Structured missing-resource/capacity/window/dependency/deadline diagnostics.
- Makespan, utilization, peak use, critical-path and search diagnostics.
- Reviewed-profile compile-and-schedule endpoint with explicit partial opt-in.
- Bounded exact branch-and-bound comparator using the same constraints.
- Canonical typed fixture and heuristic/exact parity gate.

### Remaining

- Joint plan/schedule optimization, explicit active-labor/passive-waiting
  semantics, supervision handoffs, setup/cleanup models, and product-scale
  exact/relaxation methods.

## 9. Persisted preparation operations

### Implemented

- Migration `20260801_0009`: resource-calendar versions, resources, persisted
  schedules, and append-only schedule events.
- Migration `20260801_0010`: complete schedule request payload/hash persistence.
- Migration `20260801_0011`: database lifecycle consistency constraints.
- Immutable calendar versions with explicit capacities and multi-window
  availability.
- Canonical UTC review time, reviewer, notes, content hash, request fingerprint,
  supersession, and one active reviewed calendar per household.
- Calendar activation atomically invalidates draft/approved schedules linked to
  the predecessor.
- Persisted request and response, calendar hash, occurrence-set version/hash,
  profile versions, optional source-plan version, and combined schedule hash.
- Server replay before persistence and again before approval.
- Legacy rows remain readable but approval fails closed without replay input;
  an exact matching creation retry may backfill it.
- Draft/approved/invalidated/completed/cancelled lifecycle with optimistic
  versions and append-only events.
- Owner-only calendar registration, approval, and invalidation; owner/editor
  schedule persistence, completion, and cancellation; viewer reads.
- Database rejects active drafts, missing approvers, missing invalidation
  provenance, contradictory event/status pairs, and blank event reasons.
- PostgreSQL probe covers identical calendar/schedule retries, competing
  optimistic transitions, and calendar-supersession/approval races.
- Protected frontend workspace with calendar history/registration, schedule
  ingestion, hashes, replay state, role-aware actions, task timing, and event
  history.
- Dedicated frontend/OpenAPI binding contract.

### Remaining

- First-class pipeline export into the workspace instead of JSON copy/paste.
- Calendar templates and a structured window editor.
- Occurrence-set creation from approved meal plans.
- Joint plan/calendar optimization and schedule repair.
- Execution checklists, reminders, and user-confirmed task progress; no automatic
  execution or appliance control.

## 10. Frontend

### Implemented

- One routed React/TypeScript application; obsolete JSX tree removed.
- Protected lazy routes and profile-completion routing.
- Dashboard, planner, analytics, settings, household/pantry, preparation editor,
  reviewed preparation pipeline, preparation operations, and research views.
- Role-based mutation controls and one-time invitation token retention.
- Exact leftover and evidence lifecycle provenance.
- Shared authenticated transport.
- Mechanical OpenAPI-to-TypeScript checks for evidence and preparation
  operations schemas, enums, paths, and methods.
- Vitest browser-environment coverage, skip link, labels, keyboard navigation,
  and reduced-motion handling.

### Remaining

- Authenticated Playwright/PostgreSQL end-to-end coverage, automated axe audits,
  visual regression, offline/PWA policy, internationalization, and direct
  pipeline-to-operations handoff.

## 11. Governed offline research

### Executable baselines and protocols

- TF-IDF, BM25, popularity, Bayesian popularity, content ranking, item-kNN,
  matrix factorization, MMR, Bradley-Terry, LinUCB, and Thompson sampling.
- Temporal leave-last-out ranking with hard candidate filtering and
  Recall/HitRate/MRR/NDCG, coverage, novelty, diversity, group, and violation
  metrics.
- Moving average, seasonal naive, exponential smoothing, Holt, Croston, and TSB
  with rolling-origin MAE/RMSE/sMAPE/MASE.
- Ridge, Kaplan-Meier, Mahalanobis OOD, and split conformal baselines.
- FEFO perishable-inventory replay and forecast-to-inventory closed-loop
  evaluation with forecast/service/waste leaders reported separately.
- Strict canonical benchmark documents and adversarial contract tests.
- Isolated catalog/capability import-order invariance across six clean-process
  scenarios.

### Research-only or blocked

- Vision and multimodal nutrition, constrained generation, graph-neural
  substitution, continual personalization, causal analysis, privacy attacks,
  sustainability claims, autonomous procurement, and clinical personalization.

## 12. CI and operational evidence

### Implemented configuration

- Python compileall and all backend tests.
- Repository synchronization, full Alembic chain, catalog import order,
  generated OpenAPI, and both frontend binding gates.
- Planner, preparation, ranking, forecasting, inventory, and closed-loop gates.
- Fresh SQLite/PostgreSQL migrations.
- Evidence import/lifecycle dry-run, apply, and idempotent-reapply manifests.
- PostgreSQL inventory, idempotency, preparation evidence, immutable evidence,
  evidence lifecycle, and preparation operations concurrency probes.
- Frontend lint, Vitest, Vite build, and container build.
- Machine-readable validation-report artifact retention.

### Not yet claimed

The exact latest direct-`main` workflow run has not yet been observed as complete
and green in this chat. Committed tests and configured gates must not be
reported as executed evidence until that run is inspected.

## Immediate remaining priorities

1. Inspect and close the exact latest GitHub Actions run.
2. Add authenticated Playwright/PostgreSQL end-to-end journeys and axe audits.
3. Replace JSON schedule/calendar ingestion with structured, pipeline-integrated
   editing and export.
4. Generate occurrence sets from approved plan versions with human review.
5. Expand reviewed real-recipe preparation, conversion, and storage evidence.
6. Jointly optimize meal selection, pantry lots, calendars, and preparation
   schedules while preserving hard safety and human-approval boundaries.
