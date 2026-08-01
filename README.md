# NutriFlavorOS

NutriFlavorOS is an **experimental household food-planning, inventory,
reviewed preparation-operations, immutable-evidence, and governed research
platform**. It combines deterministic meal planning, transactional household
food state, role-aware collaboration, explicit preparation resources,
replayable schedules, evidence histories, offline ranking and forecasting, and
perishable-inventory evaluation.

> **Safety boundary:** NutriFlavorOS is not clinically validated, is not a
> medical device, does not verify allergies or medication interactions, does
> not declare food safe, does not observe whether a person is present, and does
> not control appliances. Experimental and high-risk capabilities remain gated
> until their declared data, validation, human-review, approval, rollback, and
> monitoring requirements are complete.

## Synchronized repository contract

Development is performed directly on `main` in coherent commits. Code, tests,
migrations, fixtures, OpenAPI contracts, frontend bindings, capability
registrations, catalog declarations, CI, and public documentation must evolve
together. The repository does not use feature pull requests or automated
dependency-update branches.

- Database migration head: **`20260801_0011`**.
- API version: **`0.7.0`**.
- OpenAPI release contract: **`2026-08-01.4`**.
- Food-evidence frontend binding contract: **`2026-08-01.2`**.
- Preparation-operations frontend binding contract: **`2026-08-01.1`**.
- Effective governed research catalog: **`2026-08-01.3`**.

## Product platform

### Identity and household access

- Argon2 password hashing and signed JWT bearer tokens.
- Startup refusal for missing or weak signing secrets.
- Explicit profile-completion state; signup does not fabricate physiology or
  nutrition targets.
- Owner, editor, and viewer household roles.
- Unauthorized household object access returns `404`.
- Email-bound, expiring invitation secrets are stored only as hashes.
- Invitation replacement, revocation, exact-email acceptance, and retry-safe
  repeated acceptance.
- Ordinary membership workflows cannot transfer ownership.

### Transactional household food state

- Pantry lots with canonical/display names, quantity intervals, units,
  source, expiry/open timestamps, metadata, and optimistic versions.
- Leftovers linked to real recipes and optional source plans.
- Append-only purchase, consumption, discard, adjustment, leftover,
  reservation, and reservation-commit events.
- Full request fingerprints written atomically with inventory mutations.
- Contradictory idempotency-key reuse fails closed.
- Negative stock and incompatible-dimension subtraction prevention.
- Earliest-expiry allocation and expired-stock exclusion.
- Active, released, consumed, and expired stock reservations.
- Cross-plan overbooking prevention and PostgreSQL race probes.
- Shopping reconciliation and batch-preparation grouping.

### Meal planning

- Deterministic horizon-level beam search.
- Hard allergy and dietary filtering before optimization.
- Joint calorie, macro, taste, cost, cuisine, variety, repetition, and pantry
  objectives.
- Household target aggregation from complete linked profiles or explicit
  member overrides.
- Structured infeasibility and disclosed non-safety relaxation diagnostics.
- Persisted plan schema, portions, warnings, provenance, and optimizer
  diagnostics.
- Optional pantry reservation after household plan generation.
- Pareto, optional CP-SAT/MILP, robust stress, and worst-case enumeration as
  offline comparators.

## Immutable reviewed evidence

### Preparation profiles

Preparation timing, dependencies, resource demands, and unattended-cooking
suitability are never inferred from titles. Each reviewed profile retains its
recipe/schema versions, serving range, task DAG, duration interval, resource
demands, activity and supervision declarations, source, reviewer, UTC review
time, SHA-256 content hash, supersession link, and active state.

Identical same-version registration is idempotent. Contradictory reuse fails.
One active reviewed profile is permitted per recipe. Batch imports are atomic
and produce integrity-checked manifests.

### Conversion and storage-policy evidence

Migration `20260801_0007` introduced immutable ingredient-specific conversion
versions, storage-policy versions, and exact leftover-to-policy-version links.
Automatic conversion and automatic leftover expiry require exact active
reviewed evidence and return or retain the evidence ID, version, hash, source,
reviewer, and assumptions used.

Migration `20260801_0008` added append-only deactivation and rejection events.
Reactivation is deliberately unsupported; corrected evidence must be
registered as a new immutable version that supersedes the latest reviewed
predecessor, including a withdrawn predecessor.

```bash
python scripts/import_food_evidence.py reviewed-food-evidence.json
python scripts/import_food_evidence.py reviewed-food-evidence.json \
  --apply --operator reviewer@example.org

python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json
python scripts/manage_food_evidence_lifecycle.py lifecycle-actions.json \
  --apply --operator reviewer@example.org
```

Dry runs are lock-free snapshots. Apply mode acquires deterministic locks,
performs all-or-nothing writes, supports idempotent reapplication, and emits
pre- and post-commit manifests.

## Deterministic preparation scheduling

The scheduler accepts only explicit data:

- resources with capacity and one or more non-overlapping availability windows;
- tasks with duration, earliest start, deadline, priority, resource demands,
  dependencies, and provenance metadata.

It rejects duplicate/unknown/self/cyclic dependencies, missing resources,
invalid capacity, overlapping windows, and out-of-horizon declarations. The
heuristic and bounded exact comparator enforce common containing windows across
all demanded resources, prevent tasks spanning unavailable gaps, propagate
blocked dependencies, and report makespan, utilization, peak usage, critical
path bounds, unscheduled reasons, and search diagnostics.

Integrated reviewed-profile endpoint:

`POST /api/v1/preparation/compile-and-schedule`

## Persisted household preparation operations

Migrations `20260801_0009`–`20260801_0011` add the governed operational layer.

### Reviewed resource calendars

- Immutable household calendar versions.
- Explicit resource definitions, capacities, kinds, and multiple availability
  windows.
- Canonical UTC review timestamps and deterministic content hashes.
- One active reviewed calendar per household.
- Idempotent registration and exact supersession lineage.
- Activating a successor invalidates every draft or approved schedule linked to
  the predecessor in the same household transaction.

### Replayable persisted schedules

- Complete deterministic request and response payloads.
- Request hash, calendar hash, occurrence-set version/hash, optional source-plan
  version, preparation-profile versions, and combined schedule hash.
- Server replay before persistence and again before approval.
- Draft, approved, invalidated, completed, and cancelled states with optimistic
  versions.
- Append-only created/approved/invalidated/completed/cancelled events.
- Owner-only approval and invalidation; owner/editor completion and cancellation;
  viewer read access.
- Legacy `0009` schedules remain readable but approval fails closed when the
  original request is missing. An exact matching creation retry may safely
  backfill that request because the original fingerprint already binds it.

Migration `20260801_0011` enforces lifecycle consistency at the database layer:
active calendars must be reviewed, approved/completed schedules require
approver provenance, invalidated schedules require timestamp and reason, and
event action/status pairs must be valid with nonblank reasons.

Authenticated APIs are under:

`/api/v1/households/{household_id}/preparation-operations`

The protected React workspace at `/preparation/operations` provides household
selection, reviewed calendar registration, calendar history, replayable
schedule ingestion, role-aware transitions, exact hashes, legacy approval
warnings, scheduled-task timing, and append-only event history. It does not
control appliances or claim execution occurred.

See [Preparation Operations](docs/PREPARATION_OPERATIONS.md).

## Active frontend

The routed React/TypeScript application includes:

- verified authentication bootstrap and incomplete-profile routing;
- persisted-plan dashboard and descriptive analytics;
- personal meal planner;
- household members, invitations, pantry, leftovers, reservations, shopping,
  batch preparation, and inventory events;
- active-reviewed policy selection for new leftovers;
- exact leftover policy ID/version/hash/reviewer/source/scope and withdrawn
  state;
- manual preparation editor and reviewed-profile pipeline;
- persisted preparation-operations workspace;
- research catalog, runtime capability metadata, immutable conversion/policy
  histories, and lifecycle events;
- shared authenticated HTTP transport;
- lazy protected routes, skip link, keyboard navigation, and reduced-motion
  handling.

Both evidence and preparation-operations clients are checked mechanically
against generated OpenAPI for exact top-level fields, enum values, route
fragments, and HTTP methods.

## Governed research catalog

Catalog `2026-08-01.3` defines:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

Readiness is explicit: implemented, baseline available, adapter available,
research only, blocked by data, blocked by validation, or announced. Runtime
importability never means product enablement, training evidence, accuracy, or
clinical validation.

Executable offline families include TF-IDF/BM25 retrieval, popularity and
content/item-kNN/matrix-factorization ranking, MMR diversity, temporal ranking
evaluation, seasonal and intermittent-demand forecasting, uncertainty
baselines, Pareto/CP-SAT/MILP/robust planning, exact preparation comparison,
FEFO perishable-inventory replay, and forecast-to-inventory evaluation.
Policy-learning methods remain offline research only.

## Validation matrix

The direct-`main` workflow runs:

- Python compileall and all backend tests;
- repository, Alembic-chain, catalog import-order, OpenAPI, and both frontend
  binding gates;
- planner, preparation, ranking, forecasting, inventory, and closed-loop gates;
- fresh SQLite and PostgreSQL migrations;
- reviewed evidence dry-run/apply/idempotent-reapply manifests;
- PostgreSQL inventory, reservation, request-idempotency, preparation-evidence,
  immutable-evidence, evidence-lifecycle, and preparation-operations race probes;
- frontend lint, Vitest, and Vite/TypeScript build;
- container build;
- retained machine-readable backend reports.

A committed test or synthetic fixture is not a safety claim. The exact workflow
run for a commit must be inspected before describing that commit as green.

## Local setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

PostgreSQL is recommended for hosted or concurrent deployments.

## Deliberately incomplete or disabled

- Medical-condition, medication, allergy-safety, food-safety, and health-outcome
  claims are not clinically validated.
- Micronutrients are not hard optimization constraints until normalized
  provenance coverage is sufficient.
- Sustainability remains disabled without geography, production method,
  functional unit, source, and uncertainty coverage.
- Preparation capacity is persisted and scheduled but is not yet jointly
  optimized with meal selection.
- Real recipes still require reviewed preparation profiles.
- Forecasting, ranking, and inventory replay remain offline evaluation tools,
  not autonomous personalization or procurement.
- Vision, multimodal nutrition, constrained generation, graph-neural
  substitution, continual personalization, causal analysis, and privacy attacks
  remain gated research programs.
- Social, leaderboard, achievement, predictive-purchase, autonomous appliance,
  and execution-verification surfaces remain disabled.
- Authenticated Playwright end-to-end and automated accessibility coverage remain
  to be completed.
- The latest exact GitHub Actions run must still be observed before claiming the
  current `main` commit is green.

## Documentation

- [Exhaustive Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Governed Research Platform](docs/RESEARCH_PLATFORM.md)
- [Preparation Operations](docs/PREPARATION_OPERATIONS.md)
- [Optimizer Benchmarks](docs/OPTIMIZER_BENCHMARKS.md)
- [Household Access and Evidence](docs/HOUSEHOLD_ACCESS_AND_EVIDENCE.md)
