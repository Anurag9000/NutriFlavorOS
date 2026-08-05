# NutriFlavorOS Governed ML and Optimization Roadmap

**Reviewed:** 2026-08-06  
**Scope:** experimental research roadmap. Nothing in this document is a medical, food-safety, performance, savings, or production claim.

## Governing principles

1. Implement a deterministic or simple statistical baseline before a complex learned model.
2. Use household-disjoint and time-forward evaluation with point-in-time-correct features.
3. Record data license, provenance, consent, retention, deletion, and artifact hashes.
4. Require calibrated confidence, abstention, human override, rollback, and drift response.
5. Revalidate every recommendation against hard household exclusions, material availability, plan authority, and preparation constraints.
6. Never infer or recommend diagnosis, treatment, allergy status, glucose response, microbiome state, mental health, sleep treatment, or food-safety conclusions.
7. Do not scrape or ingest a third-party source unless its terms, license, freshness, and deletion requirements are reviewed.

## Priority A — optimization and scheduling

### 1. CP-SAT preparation benchmark

**Purpose:** compare the current deterministic scheduler with an exact/constraint-programming implementation on bounded fixtures.

**Required outputs:** feasible schedule, objective components, solve status, optimality gap or proof, timeout behavior, infeasibility explanation, deterministic seed, and replay manifest.

**Experiments:** resource contention, dependency chains, multiple availability windows, deadlines, partial infeasibility, large household weeks, and execution-aware repair.

### 2. MILP meal-planning benchmark

**Purpose:** establish lower/upper bounds for cost, waste, variety, leftover use, and preparation load without claiming that every real instance is solved optimally.

**Required safeguards:** explicit hard constraints, scaled units, numerical-tolerance tests, timeout fallback, and side-by-side comparison with the bounded heuristic.

### 3. Min-cost flow for material allocation

**Purpose:** assign pantry lots, leftovers, purchases, and substitutions to plan demand while minimizing expiry risk, cost, and unnecessary change.

**Features:** FEFO penalties, reservation state, package constraints, substitution edges, provenance, and explainable assignment costs.

### 4. Robust/scenario planning

**Purpose:** test plans against uncertain duration, yield, demand, price, and availability.

**Start with:** finite scenarios and stress tests. Add probabilistic models only after data quality and calibration are established.

### 5. Explainable infeasibility cores

**Purpose:** identify a minimal or near-minimal set of conflicting constraints rather than returning only “no feasible plan.”

**Outputs:** constraint IDs, affected meals/tasks/materials/resources, relaxation options, and impact estimates.

## Priority B — household forecasting

### 6. Intermittent demand baselines

Implement and compare:

- last-observation and seasonal-naive forecasts;
- simple and exponentially weighted moving averages;
- Croston, SBA, and TSB methods;
- quantile and conformal intervals.

Evaluate by household and item using MAE/MASE, pinball loss, interval coverage, stockout cost, over-purchase cost, and abstention rate.

### 7. Gradient-boosted demand and duration models

Only after baselines are established, evaluate gradient-boosted trees using lagged quantities, calendar context, plan demand, household size, package state, and reviewed execution durations.

Disallow future-derived features, random row splits, and evaluation that mixes the same household across train and test without an explicit personalization protocol.

### 8. Waste and expiry review ranking

Rank lots or leftovers for human review using deterministic expiry rules first, then compare calibrated supervised ranking if labels exist.

The model must never pronounce food safe or unsafe. It may only prioritize records using stored dates, provenance, storage metadata, and uncertainty.

## Priority C — preference and recommendation

### 9. Calibrated preference ranking

Compare popularity, recency-weighted heuristics, matrix factorization, pairwise ranking, and listwise ranking.

Required behavior:

- cold-start fallback;
- household and individual scopes kept explicit;
- confidence and abstention;
- hard exclusions applied after ranking and before presentation;
- deletion/retraining semantics for feedback;
- diversity and repetition controls reported separately from predicted preference.

### 10. Conservative contextual bandits

Defer until offline logs and counterfactual evaluation are credible. Start in shadow mode, constrain exploration, preserve deterministic fallbacks, and prohibit experimentation on high-risk exclusions or preparation authority.

### 11. Cooking-duration personalization

Use reviewed actual-vs-planned execution events to estimate household-specific task durations. Start with robust medians and quantile regression before sequence models.

Predictions must retain minimum/maximum reviewed bounds, uncertainty, and conservative scheduling policies.

## Priority D — ingredient intelligence

### 12. Typed substitution graph

Represent substitution edges by:

- functional role;
- flavor and aroma;
- texture;
- cooking process and temperature behavior;
- cuisine/context;
- quantity conversion;
- allergen and dietary properties;
- nutrient and cost impact;
- evidence source, version, confidence, and reviewer.

Use rule-based filtering plus retrieval/ranking first. A graph neural network is deferred until the graph has reliable semantics, sufficient labels, and leakage-safe evaluation.

### 13. Constraint-aware substitution validation

Every candidate must be rechecked against the whole recipe, household exclusions, available amount, units, preparation profile, equipment, and plan objectives. Low-confidence candidates remain review-only.

### 14. Retrieval-assisted recipe adaptation

Retrieve reviewed recipes and preparation profiles before any generated adaptation. Generated text must not silently alter allergens, serving calculations, cooking authority, or safety-critical instructions.

## Priority E — ingestion and perception

### 15. Barcode-assisted product entry

Use licensed lookup sources with source/version/freshness metadata. Require duplicate resolution, editable quantities, and correction history.

### 16. Constrained OCR

Use OCR to propose text fields, not to establish truth. Apply ingredient/product vocabularies, structured parsers, confidence thresholds, and mandatory review for uncertain values, dates, allergens, or quantities.

### 17. Vision-assisted ingredient suggestions

Evaluate classification or retrieval only as suggestions. Do not infer exact portion, nutrition, allergen absence, spoilage, or food safety from an image.

Required tests include lighting, occlusion, mixed dishes, packaging, unseen classes, out-of-distribution rejection, and confidence calibration.

## Priority F — data and evaluation infrastructure

### 18. Dataset registry

Each dataset entry must contain owner, purpose, source, license, consent basis, schema, time range, geography, hashes, lineage, transformations, retention, deletion, and prohibited uses.

### 19. Feature registry

Each feature must record type, unit, provenance, event time, availability time, missingness, transformation version, sensitivity, and permitted tasks.

### 20. Experiment manifests

Record code SHA, dataset and split hashes, environment lock, seed, parameters, hardware, start/end time, metrics, artifacts, and failure status. Failed and inconclusive experiments remain visible.

### 21. Evaluation suites

Include:

- household-disjoint and temporal splits;
- data-leakage and point-in-time checks;
- calibration and selective-risk curves;
- worst-household and subgroup distributions;
- robustness to missing, stale, contradictory, and adversarial inputs;
- latency, memory, cost, and throughput;
- deterministic replay and seed sensitivity;
- comparison against simple baselines;
- explicit error analysis and unsupported-use tests.

### 22. Model registry and approval

A promoted artifact requires a model card, hash, environment, evaluation report, approval record, shadow result, monitoring thresholds, rollback target, and kill switch. No learned model should directly approve plans, execute tasks, or bypass household authority.

## Deferred or prohibited proposals

The following are outside the present product boundary unless a future, independently governed clinical or regulated program is created:

- sleep-quality treatment or optimization claims;
- stress-eating or mental-health inference;
- microbiome-based or glucose-response recommendations;
- allergy diagnosis or elimination-diet planning;
- clinical biomarkers or disease-outcome prediction;
- hydration prescriptions;
- food-safety or spoilage certification;
- therapist referral logic;
- autonomous appliance operation;
- guaranteed health, savings, retention, engagement, or waste-reduction effects.

Non-clinical scheduling inputs such as user-entered availability may be used without inferring health state.

## Recommended execution sequence

1. Establish repository-claim, dataset, feature, and experiment validators.
2. Complete deterministic CP-SAT/MILP/min-cost-flow benchmarks.
3. Build intermittent-demand and duration baselines with conformal intervals.
4. Build typed substitution retrieval with full constraint revalidation.
5. Add barcode/OCR review queues and correction provenance.
6. Evaluate calibrated preference ranking in shadow mode.
7. Promote only models that pass artifact, safety, approval, and rollback gates.
8. Reconsider advanced bandits, graph models, and generation only after the evidence base justifies them.

## Success criterion

Success is not the number of model classes in the repository. Success is a smaller set of narrowly scoped systems whose data, behavior, uncertainty, authority, failure modes, and rollback are all inspectable and whose measured benefit exceeds deterministic baselines without violating household safety or privacy constraints.
