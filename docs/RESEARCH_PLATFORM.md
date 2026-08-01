# Governed Research Platform

NutriFlavorOS separates product behavior, reviewed evidence operations, and
offline research. A source file, callable, catalog entry, synthetic fixture,
passing test, or benchmark report is **not** proof that a method was trained,
promoted, clinically validated, or enabled for users.

- Database migration head: **`20260801_0011`**.
- API version: **`0.7.0`**.
- OpenAPI release contract: **`2026-08-01.4`**.
- Food-evidence frontend binding contract: **`2026-08-01.2`**.
- Preparation-operations frontend binding contract: **`2026-08-01.1`**.
- Effective research catalog: **`2026-08-01.3`**.

## Catalog inventory

The governed catalog defines:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

Readiness values are `implemented`, `baseline_available`,
`adapter_available`, `research_only`, `blocked_data`, `blocked_validation`, and
`announced`. Risk values are `low`, `moderate`, `high`, and `clinical`.

Every experiment requires data provenance and reproducibility. High-risk and
clinical experiments additionally require human review. High-risk and clinical
models cannot be default enabled.

## Catalog construction and import-order proof

The historical base declaration remains in `backend/research/catalog.py`.
`backend/research/catalog_extensions.py` applies the current additive extension
idempotently and reconstructs the full Pydantic catalog, revalidating duplicate
IDs, references, dependencies, risk gates, and prohibited defaults.

`scripts/validate_catalog_import_order.py` starts clean Python processes and
imports package, catalog, capabilities, and extension modules in six different
orders. Each scenario must produce the same version, collection IDs, counts,
and capability metadata. The full report is retained by CI.

## Mechanical capability verification

`backend/research/capabilities.py` maps every implemented or
baseline-available method to its real module and callable symbol. Verification
records dependency installation, import success, symbol presence/callability,
declared/observed status, offline availability, and product enablement.

`runtime_available=true` means only that an offline callable imports in the
current environment. Research methods remain `runtime_enabled=false` unless a
separate product path explicitly promotes them.

## Cross-contract validation

`scripts/validate_repository_contracts.py` checks:

- bidirectional catalog/capability coherence;
- core callable importability;
- catalog counts and version in public documents;
- exact migration head and one matching file;
- complete linear Alembic history with no forks, orphans, dependencies, or
  filename mismatches;
- required evidence and preparation-operations tables;
- canonical benchmark and typed evidence fixtures;
- backend OpenAPI and both frontend-binding release-contract versions;
- isolated catalog import-order invariance.

`scripts/validate_openapi_contracts.py` generates the real FastAPI document and
checks API version, required paths, exact methods, authentication, immutable
evidence mutation boundaries, required schemas, and authentication schemes.

`scripts/validate_frontend_openapi_bindings.py` compares handwritten
TypeScript clients with generated OpenAPI for exact top-level fields, enum
values, API object/binding names, route fragments, and HTTP methods. Separate
contracts cover immutable food evidence and persisted preparation operations.

## Strict canonical benchmark documents

Planner, preparation, inventory, and forecast-to-inventory fixtures use shared
strict Pydantic contracts. They reject unknown fields, duplicate identifiers,
non-finite or negative values, malformed windows, unknown dependencies or
resources, invalid policies, out-of-horizon events, SKU drift, insufficient
history/future horizons, and duplicate model IDs.

The same contracts are consumed by repository validation and executable CLIs,
so “valid fixture” cannot mean different things in different gates.

## Executable offline families

### Retrieval and ranking

- TF-IDF cosine retrieval;
- BM25 retrieval;
- popularity and Bayesian-smoothed popularity;
- explicit-content preference ranking;
- item-kNN collaborative ranking;
- matrix factorization;
- MMR diversity reranking.

Evaluation uses per-user temporal leave-last-out splitting, unseen and
hard-allowed candidates, duplicate/unknown recommendation rejection, and
post-ranking violation audits. Reports include Recall@K, HitRate@K, MRR, NDCG,
coverage, novelty, intra-list diversity, group metrics, and deterministic
fingerprints.

### Preferences and policy research

- Bradley-Terry pairwise preference model;
- LinUCB;
- Beta-Bernoulli Thompson sampling.

These remain offline comparators. Their presence does not establish logging
propensities, consent, overlap, safe policy improvement, or product approval.

### Forecasting, uncertainty, and survival

- moving average;
- seasonal naive;
- simple exponential smoothing;
- damped Holt linear trend;
- Croston and TSB intermittent demand;
- rolling-origin evaluation;
- ridge regression;
- Kaplan-Meier expiry baseline;
- Mahalanobis OOD scoring;
- split conformal regression intervals.

Rolling-origin reports retain origins, predictions, and actuals and calculate
MAE, RMSE, sMAPE, and MASE where defined.

### Planning, scheduling, and operations

- deterministic weekly beam search;
- household pantry-aware optimization;
- pure-Python Pareto enumeration;
- optional OR-Tools CP-SAT and PuLP/CBC MILP;
- planner stress testing and worst-case robust enumeration;
- immutable reviewed preparation-profile compiler;
- deterministic dependency-aware preparation scheduler;
- bounded exact branch-and-bound preparation comparator;
- deterministic FEFO perishable-inventory replay;
- forecast-to-inventory closed-loop evaluation.

## Preparation scheduling research contract

Both heuristic and exact schedulers accept explicit resource capacities and one
or more availability windows. They enforce dependencies, deadlines, cumulative
capacity, and one common containing window across every resource demanded by a
task. Tasks cannot bridge unavailable gaps.

The exact comparator minimizes lexicographically:

1. makespan;
2. total start time;
3. deterministic task/start signature.

It has explicit task/node limits and reports infeasible or search-limit states
instead of silently returning a partial optimum. Exact optimality applies only
to the bounded aligned-start fixture and configured budget.

## Persisted preparation operations as governed product state

The research scheduler is not itself an approved household operation.
Migrations `20260801_0009`–`20260801_0011` create a separate governed path:

- immutable reviewed resource-calendar versions;
- explicit capacities and multi-window availability;
- complete deterministic request and response persistence;
- request, calendar, occurrence-set, profile, plan, and combined schedule
  provenance;
- deterministic replay before persistence and approval;
- explicit draft/approved/invalidated/completed/cancelled states;
- append-only lifecycle events;
- owner/editor/viewer authorization;
- automatic invalidation on calendar supersession;
- database state-consistency constraints;
- PostgreSQL retry, transition, and supersession/approval race probes.

This path still does not infer human availability, verify that tasks occurred,
control appliances, or guarantee safety. Legacy schedules lacking the original
request remain readable but non-approvable until recreated or exactly
backfilled through the bound idempotent request.

## Planner benchmark

```bash
python scripts/benchmark_planners.py \
  --generate-seed 17 --slots 4 --options-per-slot 3 --repeats 3 \
  --max-objective-gap 1.0 \
  --output reports/experiments/planner-benchmark.json
```

The report includes deterministic input fingerprints, common-objective
re-evaluation, complete-slot and budget checks, optional dependency status,
timing, and objective gaps. Hard restrictions must be applied before every
compared solver.

## Preparation heuristic versus exact search

```bash
python scripts/benchmark_preparation_schedulers.py \
  benchmarks/preparation_scheduler_small.json \
  --require-heuristic-complete --require-exact-optimal \
  --maximum-gap-minutes 0 \
  --output reports/experiments/preparation-scheduler.json
```

The canonical fixture includes separated availability windows and proves both
methods agree under the same DAG, window, deadline, and capacity contract.

## Ranking benchmark

```bash
python scripts/benchmark_rankers.py \
  --generate-seed 17 --user-count 18 --item-group-count 3 \
  --items-per-group 8 --interactions-per-user 6 --k 5 \
  --maximum-hard-violations 0 \
  --output reports/experiments/ranking-benchmark.json
```

Accuracy, novelty, diversity, and coverage remain separate outcomes.

## Forecast and inventory evaluation

```bash
python scripts/benchmark_forecasters.py \
  --generate-seed 17 --length 84 --season-length 7 \
  --intermittent-probability 0.25 --minimum-train-size 28 \
  --horizon 7 --step 7 \
  --output reports/experiments/forecast-benchmark.json

python scripts/simulate_inventory.py \
  benchmarks/inventory_small.json \
  --minimum-fill-rate 1.0 --maximum-waste-units 1.0 \
  --maximum-stockout-units 0.0 \
  --output reports/experiments/inventory-simulation.json

python scripts/evaluate_forecast_inventory.py \
  benchmarks/forecast_inventory_small.json \
  --require-model seasonal_naive \
  --require-model tsb_intermittent_demand \
  --output reports/experiments/forecast-inventory.json
```

FEFO replay uses explicit lots, expiry days, demand, reorder rules, positive
lead times, and shelf lives. Forecast error, fill rate, stockouts, and waste are
reported separately. No benchmark selects a procurement policy automatically
or mutates household inventory.

## Evidence governance

Reviewed preparation profiles, conversions, and storage policies retain exact
versions, source/reviewer metadata, UTC review time, content hashes,
supersession, and active state. First-version and successor races are serialized
with PostgreSQL advisory locks.

Evidence import is atomic and manifest-driven. Dry runs are lock-free snapshots;
apply mode locks deterministic natural keys. Evidence deactivation/rejection is
append-only and read-only through product APIs. Reactivation is prohibited;
corrected evidence requires a new immutable successor.

## Reproducibility and CI evidence

The workflow retains repository, catalog-import-order, OpenAPI, frontend-binding,
planner, preparation, ranking, forecast, inventory, closed-loop, and manifest
reports. PostgreSQL probes cover inventory, idempotency, preparation evidence,
immutable evidence, lifecycle operations, and persisted preparation operations.

The configured workflow is not itself proof that the latest commit passed. The
exact direct-`main` run must be inspected before claiming green status.

## Research-only or blocked programs

The catalog retains explicit contracts for vision and multimodal nutrition,
constrained generation, graph-neural substitution, causal analysis,
continual/federated personalization, privacy attacks, sustainability, and
clinical personalization. They remain disabled until their data, licensing,
calibration, OOD, subgroup, privacy, human-review, external-validation,
monitoring, artifact, approval, and rollback gates are complete.
