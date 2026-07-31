# NutriFlavorOS Implementation Status

**Status date:** 2026-08-01  
**Development policy:** all work is committed directly to `main`; no feature branches or pull requests are used.  
**Current database head:** `20260801_0006`

This ledger is the repository-level source of truth for what exists, what is executable only offline, what is partially integrated, and what remains blocked. A source file, catalog record, successful import, synthetic fixture, or passing unit test is **not** evidence that a method is accurate, clinically valid, production-enabled, or safe for autonomous use.

## Status vocabulary

| Status | Meaning |
|---|---|
| **Implemented** | The product or infrastructure path is wired, persisted where required, protected by its declared access rules, and has committed contract tests. |
| **Executable offline baseline** | A deterministic or dependency-gated callable exists for research evaluation. It is not request-time enabled and has no automatic promotion path. |
| **Adapter available** | A guarded importer/client exists, but data acquisition, licensing, review, or external service configuration remains explicit. |
| **Partially implemented** | Core code exists, but at least one required integration, evaluation, operational control, or user workflow remains incomplete. |
| **Research only** | An experiment contract or architecture is defined, but training/data/evaluation/artifact gates are not complete. |
| **Blocked by data** | Suitable licensed, consented, sufficiently complete, or provenance-bearing data is absent. |
| **Blocked by validation** | Implementation may exist conceptually or partially, but safety, calibration, subgroup, OOD, human-review, or external-validation requirements are unmet. |
| **Clinical risk** | The capability must remain disabled until formal clinical governance, external validation, contraindication review, and human approval exist. |

---

## 1. Identity, authentication, profile completeness, and access control

### Implemented

- Argon2 password hashing.
- JWT bearer tokens with issuer, audience, issued-at, not-before, expiry, and unique token ID.
- Signing-key startup refusal when `SECRET_KEY` is absent or too short.
- Authenticated `/auth/me` bootstrap.
- Self-only access to user-owned resources.
- Broken-object-level-authorization prevention through `404` for inaccessible user and household resources.
- Signup captures only name, email, and password; it does not invent physiological data.
- Explicit profile-completion state and missing-field reporting.
- Profile-dependent planning fails with a structured incomplete-profile response rather than using defaults.
- Frontend authentication context verifies the server session and clears local session state immediately after `401`.
- Shared frontend HTTP transport for bearer tokens, structured FastAPI errors, validation arrays, malformed responses, network failures, and empty `204/205` responses.

### Remaining

- Password reset and verified-email workflow.
- Refresh-token rotation and token revocation ledger.
- Optional multi-factor authentication.
- Administrative support tooling with separately audited permissions.
- Full data export/delete workflow.

---

## 2. Database, migrations, integrity, and deployment verification

### Implemented

- SQLAlchemy transactional persistence for users, recipes, plans, feedback, households, invitations, members, pantry lots, leftovers, inventory events, reservations, conversions, storage policies, experiment runs, and preparation evidence.
- SQLite local-development support.
- PostgreSQL hosted/concurrent deployment path.
- Alembic migration chain through `20260801_0006`.
- Hosted startup checks exact Alembic revision, not only table presence.
- Startup refuses ORM-created hosted schemas without an Alembic revision record.
- Database constraints for:
  - household and invitation roles;
  - positive versions and serving multipliers;
  - household nutrition-target bounds;
  - pantry, event, reservation, conversion, and storage duration ranges;
  - inventory event types;
  - reservation terminal states;
  - preparation evidence status, serving coverage, immutable profile version, and active reviewed uniqueness.
- Fail-closed migration preflight for corrupt household state.
- Preparation-evidence migration backfills immutable profile versions and SHA-256 content hashes.
- One active reviewed preparation profile per recipe, enforced by a partial unique index.

### Remaining

- Automated production backup/restore drills.
- Point-in-time recovery documentation and test environment.
- Large-table migration rehearsal and lock-duration budgets.
- Data-retention schedules and purge jobs.
- Read replica and connection-pool operational guidance.

---

## 3. Household collaboration and role model

### Implemented

- User-owned households.
- `owner`, `editor`, and `viewer` roles.
- Explicit owner membership written at household creation.
- Email-bound invitation tokens stored only as SHA-256 hashes.
- One-time plaintext token handoff in the UI.
- Invitation expiry, replacement, revocation, exact-email acceptance, and retry-safe repeated acceptance.
- New invitation revokes a previous active invitation for the same account.
- Household-row locking serializes invitation and membership changes.
- Linked account membership requires invitation acceptance; direct linked-user creation is rejected.
- Owner assignment and ownership transfer are blocked from ordinary member-update APIs.
- Active member state, serving multipliers, restrictions, allergies, dislikes, and optional explicit macro targets.
- Member-update validation rejects no-op requests, blank names, invalid nulls, oversized restriction lists, and owner-role escalation.
- Household version increments for invitation/member state changes.

### Remaining

- Separately reviewed ownership-transfer workflow.
- Household deletion/archival workflow with retention policy.
- Fine-grained audit export and user-facing change history filters.
- Notification delivery for invitation creation/revocation.

---

## 4. Pantry lots, leftovers, inventory ledger, and reservations

### Implemented

- Transactional pantry lots with canonical ingredient names, display names, quantity intervals, unit, expiry/open timestamps, source, metadata, and optimistic version.
- Quantity interval preservation rather than forced point estimates.
- Append-only inventory event ledger.
- Purchase, consume, discard, absolute adjustment, leftover creation/consumption, and reservation-commit events.
- Cross-dimensional subtraction rejection.
- Negative-stock prevention.
- Expired-stock exclusion from usable inventory.
- Earliest-expiry/opened/created ordering for allocation.
- Stock reservations tied to persisted household plans.
- Reservation states: active, released, consumed, expired.
- Reservation creation subtracts active reservations from available stock.
- Reservation release, expiry, and commit are retry safe.
- Reservation commit validates lot, unit, quantity, and optimistic version before writing a consumption event.
- Plan generation does not consume inventory merely because stock was reserved.
- Cross-plan locking prevents overbooking.
- Full-request idempotency fingerprints include operation, target resource, quantities, units, reason, metadata, timestamps, and other request fields.
- Fingerprints are stamped on the ledger event in the same transaction through a SQLAlchemy `before_flush` hook.
- Contradictory idempotency-key reuse returns a structured conflict.
- Ambiguous legacy keys without a complete fingerprint are rejected.
- PostgreSQL probes cover:
  - identical concurrent retries;
  - contradictory concurrent request bodies;
  - competing optimistic versions;
  - cross-plan reservation competition;
  - duplicate reservation creation;
  - duplicate reservation commit.

### Remaining

- Multi-unit conversion during inventory allocation when reviewed ingredient-specific evidence exists.
- Barcode/receipt import with human confirmation.
- Lot splitting/merging UI.
- Recall/contamination quarantine state.
- Offline conflict resolution for disconnected clients.
- Bulk import/export and reconciliation reports.

---

## 5. Leftover and storage evidence safety

### Implemented

- Leftover batches link to real recipes and optional household plan IDs.
- Refrigerated/frozen state is explicit.
- Optional reviewed storage-policy key retained on the batch.
- Storage policy state must match the leftover storage state.
- Explicit expiry beyond a reviewed maximum is rejected.
- Frozen quality guidance is not converted into a safety-expiry timestamp.
- Unknown foods remain without a fabricated policy.
- Reviewed policy records retain food category, storage state, duration interval, maximum temperature assumption, source, URL, review date, scope, notes, and active state.
- User-facing disclaimers state that general guidance is not a guarantee of safety.

### Remaining / blocked

- Food-specific reviewed policy coverage remains incomplete.
- Preparation/cooling history is not instrumented.
- Temperature sensor integration does not exist.
- Food-safety rules remain blocked by reviewed ontology/data and clinical-grade validation.
- No autonomous “safe to eat” decision is permitted.

---

## 6. Ingredient quantities, conversions, recipes, and provenance

### Implemented

- Conservative ingredient parser stores raw text, canonical name, source interval/unit, canonical interval/unit, and parse status.
- Serving-scaled ingredient and shopping aggregation.
- Automatic conversion only across compatible dimensions.
- Ingredient-specific conversion evidence with multiplier interval, source, source version, URL, evidence status, review time, notes, and active state.
- Natural uniqueness key for conversion evidence.
- Identical conversion registration is retry safe.
- Contradictory evidence under the same natural key is rejected.
- FoodData Central portion import remains exact-food and exact-measure scoped.
- Public recipe API preserves canonical ingredient lines, servings, source name/URL/version, and nutrition basis.
- Recipe rows with invalid contracts are skipped rather than silently repaired during planning.

### Remaining

- Expand reviewed density/portion/package evidence coverage.
- Add evidence supersession/history for ingredient conversions and storage policies comparable to preparation profiles.
- Recipe data-quality dashboard.
- Provenance-aware micronutrient normalization.
- Human review workflow for ambiguous parses.

---

## 7. Personal and household meal planning

### Implemented

- Deterministic horizon-level beam search.
- Hard allergy and dietary filtering before optimization.
- Joint objective components for calories, protein, carbohydrate, fat, taste, cost, cuisine, ingredient variety, repetition, and pantry coverage.
- Household target aggregation from:
  - linked complete user profiles;
  - explicit member target overrides;
  - serving-multiplier fallback only where declared.
- Linked incomplete member profiles without explicit targets block household planning.
- Union of hard allergies/restrictions/dislikes across included members.
- Pantry coverage reported separately from nutrition/taste/cost rather than disguised as another objective.
- Persisted plan schema/provenance, portions, warnings, relaxation diagnostics, and optimizer metadata.
- Household-linked plan persistence.
- Optional inventory reservations after plan generation.
- Shopping reconciliation against lot-level inventory uncertainty.
- Batch-preparation grouping for repeated planned recipes.
- Pure-Python Pareto baseline.
- Optional CP-SAT and MILP baselines with explicit dependency availability.
- Common hard budget semantics across Pareto, CP-SAT, and MILP.
- Scenario stress testing and worst-case robust Pareto enumeration.
- Stable SHA-256 scenario fingerprints.
- Deterministic planner benchmark protocol with generated fixtures, repeated runs, common-objective audits, constraint violations, timing summaries, dependency requirements, and regression thresholds.

### Partially implemented

- Robust scenario planning is executable offline but not integrated into product plan generation.
- CP-SAT/MILP are research dependencies and not runtime planners.
- Micronutrients are not hard constraints because source completeness and normalization are insufficient.
- Preparation capacity is not yet part of the meal-selection optimizer; it is evaluated after selection through the preparation pipeline.

### Remaining

- Joint meal-selection and preparation-resource optimization.
- Distributionally robust and chance-constrained planning.
- Min-cost-flow inventory allocation across interchangeable units/lots.
- Plan repair after pantry or schedule changes.
- Explicit preference trade-off UI and Pareto frontier exploration.
- Benchmark representative household scales and infeasibility rates.

---

## 8. Reviewed preparation evidence and scheduling

### Implemented

- Explicit preparation resources with capacity and availability windows.
- Explicit tasks with duration, earliest start, deadline, priority, resource demands, dependency list, and metadata.
- Request validation for duplicate IDs, unknown dependencies, self-dependencies, and cycles.
- Deterministic dependency-aware interval-capacity scheduler.
- Topological ready-set ordering followed by deadline, priority, earliest start, and task ID.
- Dependencies constrain earliest feasible start.
- Downstream tasks receive `blocked_by_dependency` when a prerequisite is unscheduled.
- Resource capacity, availability, missing resource, excessive demand, short-window, dependency-window, and no-feasible-window diagnostics.
- Makespan, utilization, peak usage, candidate-start count, dependency-edge count, and critical-path lower-bound diagnostics.
- Reviewed recipe preparation profiles contain:
  - immutable profile version;
  - schema version;
  - reviewed serving range;
  - task-template DAG;
  - duration intervals;
  - resource demands;
  - active-work and unattended-cooking declarations;
  - source name/URL/version;
  - review time and reviewer;
  - SHA-256 content hash;
  - supersession link and active state.
- Identical profile-version retry returns the original record.
- Contradictory reuse of a profile version is rejected.
- New active reviewed versions deactivate and supersede the prior active review.
- Offline importer validates profiles before optional commit.
- Authenticated read APIs list active reviewed profiles and compile occurrences.
- Compiler refuses serving counts outside the reviewed range and does not scale durations implicitly.
- Conservative maximum duration is the default; optimistic minimum duration is disclosed as sensitivity analysis.
- Integrated `/compile-and-schedule` pipeline:
  - blocks scheduling when any occurrence is unresolved by default;
  - permits partial scheduling only through explicit `allow_partial`;
  - preserves unresolved occurrences;
  - embeds profile IDs, versions, source versions, and hashes in task/schedule diagnostics.
- Protected frontend preparation workspace for profile inspection, occurrence compilation, resource/task editing, dependency display, and schedule diagnostics.

### Remaining

- Populate reviewed profiles for real recipe records.
- Human review UI for profile creation/supersession; mutation currently remains offline-only.
- Persist user-created resource calendars.
- Integrate plan meals into occurrence generation automatically with explicit serving/deadline review.
- Model passive waiting separately from active labor and enforce unattended-cooking policy.
- Multi-person work calendars and handoff constraints.
- Optional exact RCPSP/CP-SAT scheduling baseline for benchmark comparison.
- Joint plan/schedule repair.

---

## 9. Active frontend

### Implemented

- One routed React/TypeScript application.
- Obsolete parallel JSX application, duplicate contexts, duplicate pages, and duplicate Axios client removed.
- Protected lazy routes.
- Verified auth bootstrap and explicit incomplete-profile route.
- Dashboard uses persisted data rather than fake defaults.
- Planner never auto-generates or duplicates plan state in local storage.
- Descriptive analytics avoid fabricated predictive values.
- Profile settings expose explicit required data.
- Household workspace covers members, invitations, pantry lots, leftovers, plans, reservations, shopping reconciliation, batch prep, and audit events.
- One-time invitation token remains visible until explicit dismissal.
- Role-based UI hides mutation controls for viewers.
- Preparation workspace covers reviewed profiles and dependency-aware scheduling.
- Research workspace shows catalog readiness and actual runtime capability fields.
- Shared HTTP transport and Vitest browser environment.
- Client tests for bearer tokens, structured errors, `401`, malformed JSON, empty responses, and network errors.
- Skip link, keyboard navigation, reduced-motion handling, and accessible labels on tested controls.

### Remaining

- Full browser end-to-end suite against a running backend and PostgreSQL.
- Automated accessibility audit with axe/playwright.
- Offline/PWA strategy and conflict handling.
- Internationalization and locale-aware unit/date formatting.
- Responsive visual-regression suite.
- User-facing inventory simulator and forecasting benchmark views, if later approved.

---

## 10. Executable offline research baselines

### Retrieval and ranking

- TF-IDF retriever.
- BM25 retriever.
- Popularity recommender.
- Bayesian-smoothed popularity recommender.
- Explicit-content preference ranker.
- Item-kNN collaborative recommender.
- Matrix factorization recommender.
- MMR diversity reranker.

### Preferences and policies

- Bradley–Terry pairwise preference model.
- LinUCB policy.
- Beta-Bernoulli Thompson-sampling policy.

These policy baselines remain offline-only and are not evidence that off-policy support, consent, or safety requirements are satisfied.

### Forecasting and survival

- Moving average.
- Seasonal naive.
- Simple exponential smoothing with deterministic alpha selection.
- Damped Holt linear trend.
- Croston intermittent demand.
- TSB intermittent demand.
- Rolling-origin backtesting with MAE, RMSE, sMAPE, and MASE where defined.
- Kaplan–Meier expiry baseline.

### Regression, uncertainty, and OOD

- Ridge regression.
- Mahalanobis OOD score.
- Split conformal regression intervals.

### Language and structured rules

- Ingredient parsing rules.
- Instruction DAG parser.
- Culinary substitution graph baseline.

### Optimization, scheduling, and operations

- Beam weekly optimizer.
- Household pantry-aware optimizer.
- Pareto enumeration.
- Optional OR-Tools CP-SAT.
- Optional PuLP/CBC MILP.
- Scenario stress tester.
- Worst-case robust enumeration.
- Dependency-aware preparation scheduler.
- Reviewed profile compiler.
- Deterministic FEFO perishable-inventory replay simulator.

### Governance

- Runtime capability import/symbol validation.
- Dataset/model cards.
- Group-aware and temporal splits.
- Metrics and deterministic bootstrap intervals.
- Drift diagnostics.
- Reproducible manifests.
- Cross-process-locked artifact registry with SHA-256 integrity and promotion stages.

---

## 11. Benchmark and experiment protocols

### Implemented

- Planner benchmark CLI.
- Forecasting rolling-origin benchmark CLI.
- Perishable inventory simulation CLI.
- Canonical planner and inventory fixtures.
- Regression thresholds in direct-`main` CI.
- Capability registry validation.
- Synthetic contract fixtures.

### Current catalog

The governed catalog version `2026-08-01.1` defines:

- **37 task contracts**;
- **30 dataset families**;
- **72 model/algorithm families**;
- **28 experiment contracts**;
- **37 feature contracts**.

The catalog includes implemented, baseline-available, adapter-available, research-only, data-blocked, validation-blocked, and announced entries. It does not imply artifacts or datasets are present.

### Remaining

- Versioned benchmark reports committed as release artifacts rather than generated source files.
- Scale/latency regression budgets derived from representative hardware.
- Statistical comparison across seeds and household strata.
- Forecast-to-inventory closed-loop benchmark.
- Joint planner/scheduler benchmark.
- Recommendation temporal and user-group benchmark.
- Formal experiment-result database UI.

---

## 12. Dataset and adapter state

### Implemented local/synthetic families

- Internal recipes.
- Internal inventory events.
- Internal reservations.
- Internal preparation profiles.
- Internal experiment runs.
- Synthetic contract fixtures.
- Synthetic demand series.
- Synthetic planner scenarios.
- Synthetic ranking interactions.

### Adapter available

- USDA FoodData Central adapter and exact-food portion conversion import.

### Catalogued external research families

- Recipe1M+.
- Nutrition5k.
- Food-101.
- FoodSeg103.
- DishSeg24k (release/license verification required).
- UECFOOD256.
- VireoFood172.
- Grocery Store Dataset.
- Open Food Facts.
- NHANES dietary data.
- EPIC-KITCHENS.
- Ego4D.
- AGRIBALYSE.
- ecoinvent.
- Water Footprint data.
- Food2K.
- ISIA Food-500.

No catalogued external dataset is assumed downloaded, licensed, complete, or approved merely because it appears in the registry.

---

## 13. Safety-blocked and validation-blocked capabilities

The following remain disabled or research-only:

- medical-condition and medication recommendations;
- autonomous allergen safety judgments;
- autonomous food-safety judgments;
- RGB/RGB-D nutrition estimation;
- portion estimation from images;
- food detection/segmentation product paths;
- constrained recipe generation;
- graph-neural substitution recommendations;
- contextual bandit product personalization;
- continual request-time personalization;
- N-of-1 health conclusions;
- sustainability scores without geographic and provenance coverage;
- causal claims;
- privacy-sensitive user-data modeling;
- request-time model training or artifact promotion.

Required gates vary by risk and include provenance, leakage-safe splitting, reproducibility, integrity, OOD evaluation, calibration, subgroup evaluation, human review, external validation, clinical review, documented approval, rollback, and kill switches.

---

## 14. Validation status and known uncertainty

The repository contains direct-`main` validation jobs for:

- Python compileall;
- complete backend Pytest suite;
- deterministic planner benchmark;
- rolling-origin forecasting benchmark;
- perishable inventory replay benchmark;
- fresh SQLite migration;
- fresh PostgreSQL migration;
- PostgreSQL concurrency probes;
- frontend lint, Vitest, and TypeScript/Vite build;
- container build.

At the time of this ledger update, the connected GitHub interface did not expose direct-push workflow-run logs/statuses. Therefore, this document does **not** claim that the latest complete workflow is green. The committed tests and gates are the intended executable validation contract; any failures found by GitHub Actions must be repaired directly on `main`.

---

## 15. Immediate unfinished work

1. Obtain and repair a fully green end-to-end validation run on the latest `main` head.
2. Resolve any strict TypeScript issues in dynamic preparation form fields.
3. Add a browser control for the integrated fail-closed compile-and-schedule endpoint.
4. Register and catalog the FEFO inventory simulator after benchmark review.
5. Add a canonical forecasting fixture and retained benchmark report schema.
6. Populate reviewed preparation evidence for real recipes through human review.
7. Implement forecast-to-inventory replay and joint plan-to-schedule evaluation.
8. Add accessibility and authenticated Playwright coverage.
9. Add evidence-history/versioning to conversions and storage policies.
10. Continue only gated research implementations; do not enable clinical/safety paths from synthetic success.
