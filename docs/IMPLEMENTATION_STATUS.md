# NutriFlavorOS Implementation Status

**Status date:** 2026-08-01  
**Development policy:** direct commits to `main`; no feature pull requests or
automated dependency-update branches.  
**Database migration head:** `20260801_0008`  
**OpenAPI release contract:** `2026-08-01.2`  
**Effective research catalog:** `2026-08-01.3`

Current governed inventory:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

This ledger distinguishes implemented product behavior, executable offline
baselines, adapters, research-only designs, data-blocked work,
validation-blocked work, and clinical-risk work. An importable class, source
file, synthetic fixture, or successful test is never by itself a product,
accuracy, validation, or safety claim.

## Status definitions

| Status | Meaning |
|---|---|
| Implemented | Wired through its declared product or infrastructure path with typed contracts and committed tests. |
| Executable offline baseline | Callable research comparator; not runtime enabled or automatically promoted. |
| Adapter available | Guarded client/importer exists; acquisition, licensing, review, and enablement remain explicit. |
| Partially implemented | Substantial code exists but required integration, validation, operations, or UX remains incomplete. |
| Research only | Architecture or experiment contract exists without completed data, training, artifact, evaluation, or promotion gates. |
| Blocked by data | Suitable licensed, consented, sufficiently complete, or provenance-bearing data is absent. |
| Blocked by validation | Calibration, OOD, subgroup, human-review, external-validation, or other safety gates are incomplete. |
| Clinical risk | Must remain disabled without formal clinical governance and external validation. |

## 1. Identity, authentication, and profiles

### Implemented

- Argon2 password hashing.
- JWT tokens with issuer, audience, issued-at, not-before, expiry, and token ID.
- Weak or missing signing-key refusal.
- Authenticated `/auth/me` bootstrap.
- Self-only resources and `404` object-access protection.
- Signup captures only name, email, and password.
- Explicit profile-completion and missing-field state.
- Planning refuses incomplete profiles instead of inventing values.
- Shared frontend transport with bearer tokens, structured validation errors,
  `401` invalidation, empty-response handling, malformed JSON fallback, and
  network errors.

### Remaining

- Verified email.
- Password reset.
- Token rotation/revocation.
- MFA.
- Authentication rate limits.
- Administrative support tooling.
- Full data export/delete lifecycle.

## 2. Database, migrations, and deployment integrity

### Implemented

- Transactional SQLAlchemy persistence for product and research state.
- SQLite local and PostgreSQL hosted/concurrent paths.
- Alembic chain through `20260801_0008`.
- Hosted startup requires the exact head and rejects ORM-only schemas.
- Runtime schema verification requires preparation profiles, immutable
  conversion versions, immutable storage-policy versions, exact leftover
  evidence links, and lifecycle events.
- Constraints for roles, statuses, event types, positive versions, quantity
  intervals, serving multipliers, target bounds, conversion ranges, storage
  ranges, evidence statuses, hashes, serving ranges, active reviewed
  uniqueness, lifecycle target exclusivity, and lifecycle fingerprints.
- Fail-closed household-state migration preflight.
- Preparation profile version/hash backfill.
- Conservative immutable food-evidence backfill.
- Focused `0007 → 0008 → 0007` lifecycle migration regression.
- Fresh SQLite and PostgreSQL migration jobs.

### Remaining

- Backup/restore drills.
- Point-in-time recovery.
- Large-table migration rehearsal.
- Retention/purge jobs.
- Production pool/read-replica guidance.

## 3. Household access and collaboration

### Implemented

- Household ownership and explicit owner membership.
- Owner, editor, and viewer roles.
- Hashed email-bound invitation tokens with one-time plaintext handoff.
- Expiry, replacement, revocation, exact-email acceptance, and retry-safe
  repeated acceptance.
- Household-row locking for invitation and membership races.
- Invitation-required linked accounts.
- Owner escalation and ownership transfer blocked from ordinary updates.
- Active state, serving multiplier, restrictions, allergies, dislikes, and
  optional macro targets.
- No-op, whitespace, null, oversized-list, and escalation validation.
- Household version increments.

### Remaining

- Reviewed ownership transfer.
- Household archive/deletion.
- Invitation delivery.
- User-facing audit export/filtering.

## 4. Pantry, leftovers, inventory ledger, and reservations

### Implemented

- Pantry lots with quantity intervals, units, expiry/open timestamps, source,
  metadata, and optimistic version.
- Append-only inventory events.
- Purchase, consume, discard, absolute adjustment, leftover create/consume,
  and reservation-commit events.
- Negative-stock and incompatible-unit prevention.
- Expired-stock exclusion and FEFO ordering.
- Active, released, consumed, and expired reservations.
- Cross-plan overbooking prevention.
- Retry-safe reservation creation, release, expiry, and commit.
- Complete request fingerprints including operation, target, quantity, unit,
  reason, metadata, and timestamps.
- Fingerprint written in the same transaction as the event.
- Contradictory key reuse and ambiguous legacy keys fail closed.
- PostgreSQL probes for identical and contradictory retries, stale versions,
  competing reservations, duplicate creation, and duplicate commit.

### Remaining

- Reviewed cross-unit allocation in all inventory paths.
- Receipt/barcode import.
- Lot split/merge UI.
- Recall/quarantine state.
- Offline conflict handling.
- Bulk reconciliation reports.

## 5. Immutable storage-policy and leftover evidence

### Implemented

- Versioned storage-policy history separate from the legacy compatibility table.
- Immutable `(policy_key, policy_version)` natural key.
- UTC-normalized review time and explicit reviewer.
- Source name, URL, and source version.
- Duration interval, maximum-temperature assumption, food category, storage
  state, safety scope, and notes.
- SHA-256 content hash, supersession link, and active state.
- One active reviewed version per policy key through a partial unique index.
- Identical same-version retry returns the original record.
- Contradictory same-version content fails.
- New reviewed versions supersede the latest reviewed predecessor, including a
  predecessor already deactivated or rejected.
- PostgreSQL transaction advisory locking serializes each natural key,
  including the no-existing-row race.
- Built-in reviewed policies seed as immutable `official-2026-07-31` versions.
- Concurrent built-in seeding validates the complete expected state.
- Legacy reviewed policy rows migrate conservatively; unreviewed rows remain
  preserved but inactive for automatic use.
- New leftovers select one active reviewed immutable policy version.
- Storage-state and expiry-bound validation uses that exact version.
- Exact policy ID, version, and hash are written into the leftover event.
- Exact leftover-to-policy-version link is written in the same transaction.
- Frozen quality guidance does not create a safety-expiry timestamp.
- Authorized household API resolves exact historical policy provenance.

### Remaining or blocked

- Broader food-specific policy coverage.
- Cooling and time-temperature instrumentation.
- Sensor integration.
- No autonomous “safe to eat” decision is permitted.

## 6. Immutable conversion evidence

### Implemented

- Versioned ingredient-specific conversion history.
- Natural key: canonical ingredient, source unit, target unit, record version.
- Positive multiplier interval and exact unit direction.
- Source name, URL, source version, evidence status, reviewer, UTC review time,
  and notes.
- SHA-256 content hash, supersession link, and active state.
- One active reviewed version per ingredient/unit direction.
- Idempotent identical retry and contradictory-version rejection.
- PostgreSQL natural-key advisory lock and successor-chain concurrency probe.
- Conservative legacy migration: only uniquely active reviewed conversion
  directions remain automatically eligible; ambiguous duplicates are inactive.
- Exact reviewed conversion application returns evidence ID, record version,
  content hash, source, reviewer, and output interval.
- Missing exact reviewed evidence fails rather than guessing density or package
  size.
- Read-only authenticated history and exact-conversion API.

### Remaining

- More reviewed density, portion, and package evidence.
- Ambiguous-parse review UI.
- Provenance-aware micronutrient normalization.
- Complete removal of legacy compatibility consumers after import-tree proof.

## 7. Manifest-driven immutable food-evidence import

### Implemented

- Typed `food-evidence-import-v1` document.
- Joint conversion and storage-policy import.
- Source-file SHA-256.
- Importer version and repository commit.
- Operator and reviewer identities.
- Complete natural/version keys and content hashes.
- Non-mutating database preflight.
- Deterministic natural-key lock order.
- One all-or-nothing transaction across both evidence families.
- Idempotent existing-version outcomes.
- Contradictory same-version rejection.
- Exact active/inactive predecessor supersession.
- Durable pre-apply manifest.
- Per-row planned action, outcome, record ID, active state, and supersession ID.
- Honest post-commit manifest-write failure state.
- Canonical typed CI fixture.
- CI dry-run, apply, and idempotent-reapply sequence.
- Service and CLI failure-boundary tests.

### Remaining

- Optional cryptographic document signatures and signer trust policy.
- External object-store retention for production manifests.
- Production operator access controls outside the application process.

## 8. Append-only immutable evidence lifecycle

### Implemented

- Migration `20260801_0008` and `evidence_lifecycle_events`.
- Exact conversion-or-policy target constraint.
- `deactivated` and `rejected` actions.
- Actor, reason, JSON metadata, prior active state, and creation time.
- Globally unique idempotency key.
- SHA-256 request fingerprint.
- Atomic multi-action batches.
- Deterministic idempotency and natural-key locks.
- Identical retry collapse.
- Contradictory idempotency-key rejection.
- Invalid-target whole-batch rollback.
- No evidence-content mutation.
- Reactivation prohibited; correction requires a new immutable successor.
- Durable dry-run, pending, applied, failed, and post-commit-failure manifests.
- Actor/operator equality in apply mode.
- Read-only authenticated lifecycle-history API.
- Lifecycle path is `GET` only in the OpenAPI release contract.
- PostgreSQL probes for identical retries, contradictory reuse, and concurrent
  withdrawal/successor registration.
- Historical leftover links remain readable after policy withdrawal.

### Remaining

- Optional signed lifecycle documents.
- Administrative lifecycle review UI remains intentionally absent from the
  product API.

## 9. Ingredients and recipes

### Implemented

- Conservative parser preserving raw line, canonical name, source/canonical
  intervals and units, and parse state.
- Serving-scaled shopping aggregation.
- Compatible-dimension automatic conversion only.
- Exact-food, exact-measure FoodData Central portion import into legacy
  compatibility evidence pending reviewed immutable promotion.
- Recipe API preserving canonical ingredient lines, servings, nutrition basis,
  and source provenance.
- Invalid recipe contracts are skipped rather than silently repaired during
  planning.

### Remaining

- Recipe quality/coverage dashboard.
- Reviewed parse workflow.
- Normalized micronutrient provenance.

## 10. Personal and household meal planning

### Implemented

- Deterministic horizon-level beam search.
- Hard allergy and dietary filtering before optimization.
- Calories, macros, taste, cost, cuisine, variety, repeat, and pantry objectives.
- Household aggregation from complete linked profiles and explicit overrides.
- Incomplete linked members without targets block planning.
- Union of hard restrictions.
- Pantry coverage reported separately.
- Persisted plan schema/provenance, portions, warnings, and diagnostics.
- Household-linked plans and optional reservations.
- Shopping reconciliation and batch-preparation grouping.
- Pareto, optional CP-SAT, optional MILP, scenario stress, and robust
  enumeration.
- Common hard-budget semantics and deterministic planner benchmark.

### Partially implemented

- Robust planning remains offline.
- Preparation capacity is evaluated after meal selection rather than jointly.
- Micronutrients are not hard constraints because normalized evidence coverage
  is insufficient.

### Remaining

- Joint meal/resource optimization.
- Schedule-driven repair.
- Distributionally robust or chance-constrained planning.
- Exact lot allocation.
- Pareto UI.
- Representative-scale benchmarks.

## 11. Preparation evidence and scheduling

### Implemented product path

- Immutable reviewed preparation profiles with version, schema, serving range,
  task DAG, duration interval, resource demand, active-work and unattended
  declarations, source, reviewer, UTC review time, hash, supersession, and
  active state.
- Atomic evidence-file imports with integrity-checked manifests.
- PostgreSQL identical, contradictory, and successor race probes.
- Explicit resources, capacities, availability windows, tasks, deadlines,
  priorities, demands, dependencies, and metadata.
- Duplicate, unknown, self, and cyclic dependency validation.
- Deterministic topological scheduling with cumulative capacity checks.
- Structured missing-resource, capacity, window, dependency, and feasibility
  diagnostics.
- Utilization, peak usage, makespan, critical-path lower bound, and search
  diagnostics.
- Reviewed-profile compiler with serving checks and evidence provenance.
- Conservative maximum duration default; optimistic minimum disclosed as
  sensitivity analysis.
- Fail-closed compile-and-schedule endpoint.
- Partial scheduling only through explicit opt-in.
- Manual editor and separate reviewed-evidence frontend pipeline.

### Executable exact comparator

- Branch-and-bound search over aligned starts.
- Same DAG, deadlines, resource windows, and cumulative capacities as the
  heuristic.
- Complete schedule required.
- Lexicographic minimum makespan, total start time, and deterministic signature.
- Explicit task and node budgets.
- Explicit infeasible and search-limit outcomes.
- Heuristic-versus-exact benchmark with fingerprints, determinism, timing,
  nodes, optimal makespan, and gap/ratio.
- Canonical fixture and direct-main zero-gap gate.

### Remaining

- Persisted resource calendars and approved schedules.
- Plan-to-occurrence generation with explicit human review.
- Active labor versus passive waiting, supervision, handoffs, setup/cleanup,
  and multi-person calendars.
- Joint plan/schedule repair and product-scale exact/relaxation methods.

## 12. Frontend

### Implemented

- One routed React/TypeScript app; obsolete JSX app removed.
- Protected lazy routes.
- Verified authentication and profile-completion routing.
- Evidence-driven dashboard, planner, analytics, settings, household,
  preparation, and research surfaces.
- Role-based mutation controls.
- One-time invitation token retention.
- Strict manual preparation editor and immutable preparation-evidence pipeline.
- Immutable conversion and storage-policy history views.
- Version, hash, reviewer, review time, active state, and supersession display.
- Correct catalog total rendering without readiness double counting.
- Shared transport and browser-environment Vitest tests.
- Skip link, keyboard navigation, labels, and reduced-motion behavior.

### Remaining

- Exact policy version/hash displayed beside every leftover.
- Lifecycle event history in the research screen.
- Active-reviewed immutable policy selector in the household leftover form.
- Full authenticated Playwright/PostgreSQL suite.
- Automated axe audit.
- Generated frontend schema drift validation beyond backend OpenAPI contracts.
- Offline/PWA strategy.
- Internationalization.
- Visual regression.

## 13. Ranking and recommendation evaluation

### Implemented offline baselines

- TF-IDF.
- BM25.
- Popularity.
- Bayesian popularity.
- Content preference.
- Item-kNN.
- Matrix factorization.
- MMR.

### Implemented protocol

- Seeded synthetic users, groups, items, features, interactions, and exclusions.
- Per-user temporal leave-last-out split.
- Seen and hard-excluded items removed from eligible candidates.
- Relevant held-out eligibility check.
- Duplicate and unknown recommendation rejection.
- Post-ranking hard-violation counts.
- Recall@K, HitRate@K, MRR, NDCG, catalog coverage, novelty, diversity, group
  metrics, and deterministic fingerprints.
- Separate accuracy, diversity, and coverage leaders.
- Direct-main hard-violation and wiring gate.

### Remaining

- Real consented temporal interactions.
- User-kNN.
- Implicit ALS/BPR.
- Sequential models.
- Calibration.
- Uncertainty/abstention.
- Product-safe preference workflows.

## 14. Forecasting, inventory replay, and closed-loop evaluation

### Implemented forecasting

- Moving average, seasonal naive, simple exponential smoothing, damped Holt,
  Croston, TSB, rolling-origin evaluation, and forecast metrics.
- Seeded synthetic seasonal/intermittent generation and regression-gated CLI.

### Implemented inventory replay

- Deterministic FEFO replay with explicit arrivals, expiry, demand, reorder
  decisions, and end-of-day accounting.
- Stockout, waste, fill rate, service level, average inventory, per-SKU metrics,
  event ledger, and input fingerprint.
- Non-mutating CLI and canonical fixture.

### Implemented closed loop

- Common realized demand path.
- Forecast-to-explicit-base-stock translation.
- Forecast metrics separated from inventory outcomes.
- Separate forecast, fill-rate, and waste leaders.
- Deterministic evaluation fingerprints and direct-main gate.

### Remaining

- SBA.
- ADIDA and IMAPA.
- Theta.
- Optional ARIMA/ETS.
- Forecast intervals.
- Hierarchical reconciliation.
- Economic costs.
- Stochastic lead times.
- Substitutions.
- Storage capacity.
- Richer policy frontiers.

## 15. Research governance and catalog

### Implemented

- Effective validated catalog `2026-08-01.3` with 37 tasks, 30 datasets,
  75 models, 29 experiments, and 39 features.
- Additive extension layer reconstructing and revalidating the complete catalog.
- Runtime callable registry with import and symbol verification.
- Dataset/model cards, deterministic splits, metrics, drift, manifests, and
  experiment-run state.
- Cross-process artifact registry with integrity checks and promotion stages.
- Repository contract validator covering catalog, capabilities, docs,
  migration head, required tables, benchmark fixtures, typed evidence fixtures,
  and release-contract versions.
- Generated OpenAPI validator covering paths, methods, security, immutable
  mutation boundaries, and required provenance/lifecycle fields.

### External dataset status

- Implemented local/synthetic families: internal recipes, inventory,
  reservations, preparation profiles, experiment runs, contract fixtures,
  demand series, planner scenarios, and ranking interactions.
- USDA FoodData Central adapter available.
- Other external dataset records remain contracts until license, acquisition,
  hashing, cards, quality, privacy, and approval are complete.

## 16. Validation contract and honesty

Direct-main validation includes:

- Python compileall and all backend tests;
- repository contract validation;
- generated OpenAPI validation;
- planner, exact preparation, ranking, forecasting, inventory, and closed-loop
  benchmark gates;
- fresh SQLite and PostgreSQL migrations;
- reviewed food-evidence dry-run/apply/idempotent-reapply manifests;
- lifecycle dry-run/apply/idempotent-reapply manifests;
- PostgreSQL inventory, reservation, request-idempotency,
  preparation-evidence, immutable-version, and lifecycle concurrency probes;
- frontend lint, tests, and build;
- container build;
- retained backend JSON reports.

This ledger does **not** claim that the latest complete workflow is green until
the exact run is inspected.

## 17. Safety-blocked work

Still disabled or research-only:

- medical or medication recommendations;
- autonomous allergy or food-safety judgments;
- image-based nutrition and portion claims;
- constrained recipe generation;
- graph-neural substitution product behavior;
- contextual-bandit product personalization;
- request-time continual learning;
- N-of-1 health conclusions;
- incomplete-provenance sustainability scores;
- causal claims;
- privacy-sensitive modeling;
- request-time model training or promotion.

## 18. Immediate unfinished work

1. Inspect and repair one exact complete direct-main workflow run.
2. Expose exact leftover policy ID/version/hash and lifecycle events in the
   frontend.
3. Move the household policy selector to active reviewed immutable versions.
4. Add generated frontend/OpenAPI schema drift validation.
5. Persist reviewed household resource calendars and approved schedules.
6. Add authenticated Playwright/PostgreSQL and axe coverage.
7. Expand reviewed conversion and storage-policy coverage.
8. Add evidence coverage and abstention dashboards.
9. Expand stochastic inventory costs and closed-loop evaluation.
10. Build consent-based real-data ranking workflows.
11. Continue high-risk research only through explicit data, evaluation,
    artifact, approval, rollback, and monitoring gates.
