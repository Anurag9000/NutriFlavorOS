# Governed Research Platform

NutriFlavorOS separates runtime product behavior from offline research
evaluation. A source file, importable callable, catalog entry, synthetic
fixture, or passing benchmark is **not** evidence that a method was trained,
promoted, clinically validated, or enabled for users.

- Current database migration head: **`20260801_0007`**.
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

## Base catalog and validated extensions

The historical base declaration remains in `backend/research/catalog.py`.
`backend/research/catalog_extensions.py` applies the current additive extension
once when `backend.research` loads. The extension reconstructs the complete
Pydantic catalog, so duplicate IDs, broken references, invalid feature
dependencies, missing risk gates, and prohibited high-risk defaults are
revalidated on the effective catalog.

The current extension adds:

- exact bounded preparation scheduling;
- deterministic FEFO inventory replay;
- forecast-to-inventory closed-loop evaluation;
- their experiment and feature connections.

Repeated extension application is idempotent and covered by catalog
reconstruction tests.

## Mechanical capability verification

`backend/research/capabilities.py` declares the real module and callable symbol
for every implemented or baseline-available method. The verifier records:

- dependency class and installation state;
- module import success;
- symbol presence and callability;
- declared and observed status;
- offline runtime availability;
- product runtime enablement.

`runtime_available=true` means only that an offline callable imports in the
current environment. `runtime_enabled` remains false for research methods.

`scripts/validate_repository_contracts.py` additionally checks:

- bidirectional catalog/capability coherence;
- importability of every core callable;
- catalog version and collection counts in public documentation;
- current Alembic revision and exactly one matching migration file;
- required immutable-evidence tables in the runtime schema contract;
- required benchmark fixture presence and JSON-object shape.

```bash
python scripts/validate_repository_contracts.py
```

## Executable offline baseline families

### Retrieval and ranking

- TF-IDF cosine retrieval;
- BM25 retrieval;
- popularity ranking;
- Bayesian-smoothed popularity;
- explicit-content preference ranking;
- item-kNN collaborative ranking;
- matrix factorization;
- MMR diversity reranking.

The ranking evaluator uses per-user temporal leave-last-out splitting, unseen
and hard-allowed candidate sets, duplicate and unknown recommendation
rejection, and post-ranking hard-violation audits. It reports Recall@K,
HitRate@K, MRR, NDCG, catalog coverage, novelty, intra-list diversity,
user-group metrics, and deterministic fingerprints.

### Preferences and policy research

- Bradley-Terry pairwise preference model;
- LinUCB;
- Beta-Bernoulli Thompson sampling.

These remain offline comparators. Their presence does not establish logging
propensities, overlap, consent, safe policy improvement, or product approval.

### Forecasting, uncertainty, and survival

- moving average;
- seasonal naive;
- simple exponential smoothing with deterministic alpha selection;
- damped Holt linear trend;
- Croston intermittent demand;
- TSB intermittent demand;
- rolling-origin evaluation;
- ridge regression;
- Kaplan-Meier expiry baseline;
- Mahalanobis OOD scoring;
- split conformal regression intervals.

Rolling-origin reports retain forecast, actual, and origin arrays and calculate
MAE, RMSE, sMAPE, and MASE where a valid seasonal-naive scale exists.

### Language and graph rules

- conservative ingredient parser;
- instruction dependency DAG parser;
- culinary substitution graph baseline.

### Planning, scheduling, and operations

- deterministic weekly beam search;
- household pantry-aware optimization;
- pure-Python Pareto enumeration;
- optional OR-Tools CP-SAT;
- optional PuLP/CBC MILP;
- planner scenario stress testing;
- worst-case robust enumeration;
- immutable reviewed preparation-profile compiler;
- dependency-aware product preparation scheduler;
- exact branch-and-bound scheduler for bounded aligned-start fixtures;
- deterministic FEFO perishable-inventory replay;
- forecast-to-inventory closed-loop evaluation.

## Planner benchmark

`scripts/benchmark_planners.py` provides deterministic synthetic generation,
SHA-256 input fingerprints, repeated execution, common-objective
re-evaluation, complete-slot and hard-budget checks, deterministic replay,
timing summaries, optional-dependency gates, objective-gap thresholds, and
machine-readable reports.

```bash
python scripts/benchmark_planners.py \
  --generate-seed 17 --slots 4 --options-per-slot 3 --repeats 3 \
  --max-objective-gap 1.0 \
  --output reports/experiments/planner-benchmark.json
```

Hard allergy and dietary filtering must occur before every compared solver.

## Preparation heuristic versus exact search

`backend/research/exact_preparation_scheduler.py` performs exhaustive
aligned-start branch-and-bound search for bounded fixtures. It uses the same
validated dependency DAG, deadlines, resource windows, and cumulative
capacities as the deterministic product heuristic.

Its objective is lexicographic:

1. minimum makespan;
2. minimum total start time;
3. deterministic task/start signature.

The solver has explicit task and node budgets. It reports infeasible and
search-limit outcomes instead of silently returning a partial optimum.

```bash
python scripts/benchmark_preparation_schedulers.py \
  benchmarks/preparation_scheduler_small.json \
  --require-heuristic-complete --require-exact-optimal \
  --maximum-gap-minutes 0 \
  --output reports/experiments/preparation-scheduler.json
```

Exact optimality applies only to the bounded aligned-start fixture contract and
the configured search budget.

## Ranking benchmark

`scripts/benchmark_rankers.py` creates or loads a leakage-safe fixture and
compares popularity, Bayesian popularity, item-kNN, and MMR on the same
candidate filters and temporal split.

```bash
python scripts/benchmark_rankers.py \
  --generate-seed 17 --user-count 18 --item-group-count 3 \
  --items-per-group 8 --interactions-per-user 6 --k 5 \
  --require-model bayesian_popularity_recommender \
  --require-model item_knn_recommender \
  --require-model mmr_diversity_reranker \
  --maximum-hard-violations 0 \
  --output reports/experiments/ranking-benchmark.json
```

Accuracy, novelty, diversity, and coverage are never collapsed into a single
product-selection claim.

## Forecast benchmark

`scripts/benchmark_forecasters.py` provides deterministic
seasonal/intermittent series generation, a SHA-256 series fingerprint, common
rolling origins and horizons, six baseline factories, complete
prediction/actual/origin retention, required-model checks, MAE regression
thresholds, and JSON reports.

```bash
python scripts/benchmark_forecasters.py \
  --generate-seed 17 --length 84 --season-length 7 \
  --intermittent-probability 0.25 --minimum-train-size 28 \
  --horizon 7 --step 7 \
  --require-model seasonal_naive \
  --require-model tsb_intermittent_demand \
  --output reports/experiments/forecast-benchmark.json
```

Forecast accuracy is not assumed to imply lower stockout or waste.

## Perishable inventory replay

`backend/research/inventory_simulation.py` accepts explicit initial lots,
expiry days, demand events, reorder points, order-up-to levels, positive
supplier lead times, replenishment shelf lives, and a replay horizon.

Daily sequence:

1. receive arrivals;
2. remove expired lots;
3. allocate realized demand FEFO;
4. record unfulfilled demand;
5. place explicit policy orders;
6. record end-of-day inventory.

It reports demand, fulfillment, stockouts, expired waste, orders, ending
inventory, fill rate, demand-event service level, average on-hand inventory,
per-SKU metrics, a deterministic event ledger, and an input fingerprint.

```bash
python scripts/simulate_inventory.py \
  benchmarks/inventory_small.json \
  --minimum-fill-rate 1.0 \
  --maximum-waste-units 1.0 \
  --maximum-stockout-units 0.0 \
  --output reports/experiments/inventory-simulation.json
```

The simulator never mutates household inventory.

## Forecast-to-inventory closed loop

`backend/research/forecast_inventory_pipeline.py` evaluates the offline chain:

1. fit a declared forecasting baseline;
2. forecast a fixed future horizon;
3. translate the forecast through an explicit base-stock rule;
4. replay the same realized demand through FEFO inventory;
5. report forecast and operational outcomes separately.

```bash
python scripts/evaluate_forecast_inventory.py \
  benchmarks/forecast_inventory_small.json \
  --require-model seasonal_naive \
  --require-model tsb_intermittent_demand \
  --minimum-best-fill-rate 0.80 \
  --maximum-least-waste 2.0 \
  --output reports/experiments/forecast-inventory.json
```

The forecast leader, fill-rate leader, and least-waste leader remain separate.
No procurement policy is selected automatically.

## Immutable reviewed evidence

### Preparation profiles

Every reviewed preparation profile retains recipe ID, immutable profile
version, schema version, serving range, task DAG, duration interval, resource
demands, active-work and unattended-cooking declarations, source provenance,
reviewer, UTC review time, SHA-256 content hash, supersession link, and active
state.

Rules:

- identical same-version retries return the original record;
- contradictory same-version content is rejected;
- one active reviewed profile per recipe is database-enforced;
- new reviewed versions deactivate and supersede the prior active review;
- evidence-file imports are all-or-nothing;
- ordinary API users cannot mutate global preparation evidence;
- PostgreSQL probes cover identical, contradictory, and successor races.

```bash
python scripts/import_preparation_profiles.py reviewed-profiles.json
python scripts/import_preparation_profiles.py reviewed-profiles.json \
  --apply --operator reviewer@example.org
```

The importer writes a source-file hash, operator, reviewer identities, natural
keys, content hashes, planned actions, outcomes, commit identity, and manifest
hash. A durable pre-apply manifest is written before database mutation.

### Conversion and storage-policy histories

Migration `20260801_0007` introduces immutable conversion versions, immutable
storage-policy versions, and exact leftover-to-policy-version links.

Reviewed records retain natural evidence keys, immutable versions, source
provenance, UTC review metadata, SHA-256 hashes, supersession links, and active
state. One active reviewed conversion exists per ingredient/unit direction and
one active reviewed policy exists per policy key.

Registration uses PostgreSQL transaction advisory locks per natural key, which
protects the first-version race that row locks cannot cover. Identical
concurrent retries collapse, contradictory same-version content conflicts, and
concurrent successor versions form one supersession chain with one active
review.

Automatic immutable conversion requires an exact active reviewed record and
returns its evidence ID, version, and content hash. New leftovers validate
against one active reviewed storage policy and persist the exact policy link
and event-ledger provenance in the same transaction. Frozen quality guidance
is not converted into a safety expiry.

The public API is read-only except for applying an already reviewed exact
conversion. Global evidence registration and supersession remain offline
reviewed operations.

## Integrated preparation pipeline

`POST /api/v1/preparation/compile-and-schedule` performs active reviewed
profile selection, serving-range validation, task namespacing, conservative or
disclosed sensitivity duration selection, deterministic scheduling, and
evidence-provenance propagation.

Default behavior is fail closed. Any unresolved occurrence blocks the schedule.
Partial scheduling requires explicit `allow_partial=true`; unresolved records
remain in the response and schedule diagnostics.

## Dataset contracts and leakage controls

Implemented local/synthetic families include internal recipes, inventory,
reservations, preparation profiles, experiment runs, synthetic contract
fixtures, demand series, planner scenarios, and ranking interactions.

External records are contracts only until acquisition, license review, hashing,
cards, quality audits, and approval are complete. Catalogued families include
USDA FoodData Central, Recipe1M+, Nutrition5k, Food-101, FoodSeg103,
UECFOOD256, VireoFood172, Grocery Store Dataset, Open Food Facts, NHANES,
EPIC-KITCHENS, Ego4D, AGRIBALYSE, ecoinvent, Water Footprint data, Food2K,
ISIA Food-500, and announced DishSeg24k.

Supported deterministic split contracts include group-aware holdout, temporal
holdout, rolling-origin evaluation, and versioned scenario fixtures. Future
adapters must declare grouping entity, timestamp semantics, duplicate policy,
source-version boundary, split fingerprint, and leakage audit.

## Cards, manifests, and artifact registry

Dataset/model cards retain source, license, tasks, modalities, risk, readiness,
prerequisites, limitations, and intended offline use. Experiment manifests
retain identifiers, seeds, validated configuration, environment snapshots,
dataset/model fingerprints, metrics, warnings, and artifacts.

The artifact registry provides SHA-256 verification,
registered/candidate/champion/archived/rejected stages, risk-dependent promotion
gates, cross-process locking, fsync and atomic replacement, one champion,
archived prior winners, and rollback metadata. Drift or benchmark success
cannot retrain or promote automatically.

## Direct-main validation

The validation workflow runs:

- Python compileall and all backend tests;
- repository contract validation;
- planner benchmark;
- exact preparation comparison;
- temporal ranking benchmark;
- forecasting benchmark;
- perishable inventory replay;
- forecast-to-inventory replay;
- fresh SQLite and PostgreSQL migrations;
- inventory, reservation, request-idempotency, preparation-evidence, and
  immutable food-evidence PostgreSQL concurrency probes;
- frontend lint, tests, and build;
- container build;
- retained machine-readable backend reports.

This document does not claim the latest commit is green unless its exact
workflow result has been inspected.

## Promotion requirements

Before any research method becomes a runtime candidate, it requires licensed
or consented versioned data, leakage-safe splits, baseline comparison,
deterministic or seeded replay, appropriate uncertainty/calibration, subgroup
and OOD evaluation where relevant, an integrity-checked artifact, cards and
limitations, risk-proportional human review, explicit candidate/champion
decision, rollback/kill switch, and product-specific authorization and
monitoring.

Clinical-risk capabilities additionally require formal clinical governance and
external validation. Synthetic success is never sufficient.

See also:

- [Implementation Status](IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](ROADMAP.md)
- [Optimizer Benchmarks](OPTIMIZER_BENCHMARKS.md)
- [Household Access and Evidence](HOUSEHOLD_ACCESS_AND_EVIDENCE.md)
