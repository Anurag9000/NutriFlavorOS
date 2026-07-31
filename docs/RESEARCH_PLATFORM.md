# Governed Research Platform

NutriFlavorOS separates **runtime product behavior** from **offline research evaluation**. The research platform is designed to prevent a source file, catalog entry, synthetic result, or importable class from being mistaken for a trained, promoted, clinically valid, or product-enabled capability.

## Current catalog

Catalog version: `2026-08-01.1`

- **37 task contracts**
- **30 dataset families**
- **72 model and algorithm families**
- **28 experiment contracts**
- **37 product/research feature contracts**

Readiness values are explicit:

- `implemented`
- `baseline_available`
- `adapter_available`
- `research_only`
- `blocked_data`
- `blocked_validation`
- `announced`

Risk values are explicit:

- `low`
- `moderate`
- `high`
- `clinical`

No high-risk or clinical model is default enabled. Every experiment requires data provenance and reproducibility gates; high-risk and clinical experiments additionally require human review.

## Runtime capability verification

`backend/research/capabilities.py` is the executable capability inventory. Each entry declares:

- module path;
- callable symbol;
- declared status;
- dependency class;
- whether the dependency is installed;
- whether the module imports;
- whether the symbol exists and is callable;
- runtime availability;
- runtime enablement.

`runtime_available=true` means only that an offline callable can be imported in the current environment. `runtime_enabled` remains false for research methods.

CI verifies:

- every catalogued implemented/baseline model has a capability registration;
- every capability registration has a catalog model;
- every core registration imports and resolves to a callable;
- optional CP-SAT/MILP registrations remain valid when their dependency is absent.

## Executable baseline families

### Retrieval

- TF-IDF cosine retrieval.
- BM25 retrieval.

### Recommendation and ranking

- popularity;
- Bayesian-smoothed popularity;
- content preference;
- item-kNN collaborative filtering;
- matrix factorization;
- MMR diversity reranking.

### Preference and policy research

- Bradley–Terry pairwise preferences;
- LinUCB;
- Beta-Bernoulli Thompson sampling.

These are offline comparators. They do not authorize request-time policy learning or deployment.

### Forecasting

- moving average;
- seasonal naive;
- simple exponential smoothing;
- damped Holt trend;
- Croston intermittent demand;
- TSB intermittent demand;
- rolling-origin backtesting.

The backtest reports MAE, RMSE, sMAPE, and MASE where the seasonal-naive scale is defined. It preserves origins, actuals, and predictions.

### Regression, uncertainty, and OOD

- ridge regression;
- split conformal intervals;
- Mahalanobis OOD scoring;
- Kaplan–Meier expiry/survival baseline.

### Language and graph rules

- ingredient quantity parsing;
- instruction dependency DAG parsing;
- substitution graph suggestions.

### Planning and operations

- deterministic weekly beam search;
- household pantry-aware optimization;
- Pareto enumeration;
- optional OR-Tools CP-SAT;
- optional PuLP/CBC MILP;
- scenario stress testing;
- worst-case robust enumeration;
- dependency-aware preparation scheduling;
- reviewed preparation profile compilation;
- deterministic FEFO perishable-inventory replay simulation.

## Planner benchmark protocol

`scripts/benchmark_planners.py` supports:

- deterministic synthetic scenario generation;
- versioned input fingerprints;
- repeated solver execution;
- common objective re-evaluation;
- slot-selection validity;
- hard budget checks;
- deterministic replay checks;
- elapsed-time distributions;
- objective-gap thresholds;
- required solver/dependency gates;
- machine-readable JSON reports.

Canonical fixture: `benchmarks/planner_small.json`.

Example:

```bash
python scripts/benchmark_planners.py \
  --generate-seed 17 \
  --slots 4 \
  --options-per-slot 3 \
  --repeats 3 \
  --max-objective-gap 1.0 \
  --output reports/experiments/planner-benchmark.json
```

Hard allergy/dietary filtering is expected upstream and must be identical for every compared solver.

## Forecast benchmark protocol

`scripts/benchmark_forecasters.py` supports:

- deterministic seasonal/intermittent synthetic generation;
- input series SHA-256 fingerprint;
- common rolling origins and horizons;
- six baseline factories;
- complete prediction/actual/origin retention;
- required-model checks;
- maximum-MAE regression threshold;
- machine-readable report and optional retained input series.

Example:

```bash
python scripts/benchmark_forecasters.py \
  --generate-seed 17 \
  --length 84 \
  --season-length 7 \
  --intermittent-probability 0.25 \
  --minimum-train-size 28 \
  --horizon 7 \
  --step 7 \
  --require-model seasonal_naive \
  --require-model tsb_intermittent_demand \
  --output reports/experiments/forecast-benchmark.json
```

Forecast accuracy is not treated as evidence of lower operational waste or stockouts. Closed-loop inventory replay remains a separate experiment.

## Perishable inventory simulation protocol

`backend/research/inventory_simulation.py` evaluates explicit:

- initial lots;
- expiry days;
- demand events;
- reorder points;
- order-up-to levels;
- positive supplier lead times;
- replenishment shelf lives;
- simulation horizon.

Daily sequence:

1. arrivals;
2. expiry removal;
3. FEFO demand allocation;
4. stockout recording;
5. reorder decision;
6. end-of-day inventory accounting.

Reported metrics:

- demand and fulfilled units;
- stockout units and events;
- expired/waste units;
- ordered and ending units;
- fill rate;
- demand-event service level;
- average on-hand inventory;
- per-SKU metrics;
- deterministic event ledger;
- SHA-256 input fingerprint.

CLI:

```bash
python scripts/simulate_inventory.py \
  benchmarks/inventory_small.json \
  --minimum-fill-rate 1.0 \
  --maximum-waste-units 1.0 \
  --maximum-stockout-units 0.0 \
  --output reports/experiments/inventory-simulation.json
```

The simulator never writes to household inventory.

## Reviewed preparation evidence

Preparation evidence is versioned separately from recipes.

Every profile retains:

- recipe ID;
- immutable profile version;
- schema version;
- reviewed serving range;
- task-template DAG;
- minimum/maximum durations;
- resource demands;
- active-work flag;
- unattended-cooking declaration or explicit unknown;
- source name/URL/version;
- evidence status;
- review timestamp and reviewer;
- SHA-256 content hash;
- supersession link;
- active state.

Rules:

- reviewed timestamps must be timezone-aware and normalize to UTC;
- the same `(recipe_id, profile_version)` with identical content is idempotent;
- contradictory reuse is rejected;
- one active reviewed profile per recipe is enforced in the database;
- new active reviewed versions deactivate and supersede the prior review;
- ordinary API users cannot mutate global evidence;
- import is performed through the offline validated CLI;
- duration and resource values are never inferred from a title or instruction string.

Import dry run:

```bash
python scripts/import_preparation_profiles.py reviewed-profiles.json
```

Apply after review:

```bash
python scripts/import_preparation_profiles.py reviewed-profiles.json --apply
```

## Integrated evidence-to-schedule pipeline

`POST /api/v1/preparation/compile-and-schedule` combines:

1. reviewed profile lookup;
2. serving-range validation;
3. task DAG namespacing;
4. conservative or sensitivity duration selection;
5. resource scheduling;
6. provenance propagation.

Default behavior is fail-closed. If any occurrence lacks an eligible profile, is outside the reviewed serving range, or otherwise cannot compile, no schedule is created. Partial execution requires explicit `allow_partial=true`; unresolved occurrences remain in the response and diagnostics.

## Dataset contracts

Implemented local/synthetic families include:

- internal recipes;
- internal inventory;
- internal reservations;
- internal preparation profiles;
- internal experiment runs;
- synthetic contract fixtures;
- synthetic demand series;
- synthetic planner scenarios;
- synthetic ranking interactions.

External families are catalog contracts only until acquisition, licensing, hashing, card creation, and review are complete. They include USDA FoodData Central, Recipe1M+, Nutrition5k, Food-101, FoodSeg103, UECFOOD256, VireoFood172, Grocery Store Dataset, Open Food Facts, NHANES, EPIC-KITCHENS, Ego4D, AGRIBALYSE, ecoinvent, Water Footprint data, Food2K, ISIA Food-500, and announced DishSeg24k.

## Dataset splits and leakage controls

Supported deterministic split contracts include:

- group-aware holdout;
- temporal split;
- rolling-origin time-series evaluation;
- versioned scenario fixture split.

Future adapters must define:

- grouping entity;
- timestamp semantics;
- duplicate/near-duplicate policy;
- source-version boundary;
- train/validation/test fingerprint;
- leakage audit.

## Metrics

The metrics layer includes retrieval/ranking, forecasting, regression, calibration, uncertainty, segmentation, drift, and offline-policy measures. Experiment contracts identify primary metrics, but metric presence does not establish appropriateness; each experiment must justify its metric set and risk-sensitive failure modes.

## Cards, manifests, registry, and artifacts

### Dataset cards

Cards retain source, license, tasks, modalities, personal-data status, version, readiness, and limitations.

### Model cards

Cards retain family, tasks, risk, readiness, prerequisites, limitations, and intended offline use.

### Manifests

Experiment manifests retain:

- experiment/model identifiers;
- seed;
- validated config;
- environment snapshot;
- dataset/model fingerprints;
- metrics;
- warnings;
- artifacts.

### Artifact registry

The registry provides:

- dataset/model registration;
- SHA-256 integrity verification;
- registered, candidate, champion, archived, and rejected stages;
- risk-dependent promotion gates;
- cross-process file locking;
- fsync and atomic replacement;
- single champion with archived prior winner;
- rollback information.

Promotion is always explicit. Drift or benchmark success cannot retrain or promote automatically.

## Offline runner

The runner accepts only whitelisted baseline identifiers and guarded data paths. It rejects arbitrary experiment code and user runtime-data paths. The API validates experiment configs and previews manifests but does not execute arbitrary jobs.

## Direct-main validation

The validation workflow runs:

- Python compileall;
- all backend tests;
- planner benchmark gate;
- forecasting benchmark gate;
- inventory replay gate;
- fresh SQLite migration;
- fresh PostgreSQL migration;
- PostgreSQL inventory/reservation concurrency probe;
- full-request idempotency concurrency probe;
- frontend lint, tests, and build;
- container build.

No statement in this document claims the latest run is green unless an exact workflow result is inspected.

## Promotion requirements

Before any research method becomes a runtime candidate, it requires:

1. licensed/consented/versioned data;
2. leakage-safe split;
3. baseline comparison;
4. deterministic or seeded replay;
5. appropriate uncertainty and calibration;
6. subgroup and OOD evaluation where relevant;
7. integrity-checked artifact;
8. card and limitations;
9. human review proportional to risk;
10. explicit candidate/champion decision;
11. rollback path and kill switch;
12. product-specific authorization and monitoring.

Clinical-risk capabilities additionally require formal clinical governance and external validation. Synthetic success is never sufficient.

See also:

- [Implementation Status](IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](ROADMAP.md)
- [Optimizer Benchmarks](OPTIMIZER_BENCHMARKS.md)
- [Household Access and Evidence](HOUSEHOLD_ACCESS_AND_EVIDENCE.md)
