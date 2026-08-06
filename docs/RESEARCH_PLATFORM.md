# Governed Research Platform

NutriFlavorOS separates product behavior, reviewed evidence operations, and offline research. A source file, callable, catalog entry, synthetic fixture, passing test, or benchmark report is **not** proof that a method was trained, promoted, clinically validated, safe, or enabled for users.

- Database migration head: **`20260802_0018`**.
- API version: **`0.12.1`**.
- OpenAPI release contract: **`2026-08-02.6`**.
- Food-evidence frontend binding contract: **`2026-08-01.2`**.
- Preparation-operations frontend binding contract: **`2026-08-02.4`**.
- Household-plan frontend binding contract: **`2026-08-02.4`**.
- Effective research catalog: **`2026-08-01.3`**.

## Catalog inventory

The governed catalog defines:

- **37 task contracts**;
- **30 dataset families**;
- **75 model/algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

Readiness values are `implemented`, `baseline_available`, `adapter_available`, `research_only`, `blocked_data`, `blocked_validation`, and `announced`. Risk values are `low`, `moderate`, `high`, and `clinical`.

Every experiment requires data provenance and reproducibility. High-risk and clinical experiments additionally require human review. High-risk and clinical models cannot be default enabled.

## Catalog construction and import-order proof

The historical base declaration remains in `backend/research/catalog.py`. `backend/research/catalog_extensions.py` applies the current additive extension idempotently and reconstructs the full Pydantic catalog, revalidating duplicate IDs, references, dependencies, risk gates, and prohibited defaults.

`scripts/validate_catalog_import_order.py` starts clean Python processes and imports package, catalog, capabilities, and extension modules in multiple orders. Every scenario must produce identical versions, collection IDs, counts, and capability metadata.

## Mechanical capability verification

`backend/research/capabilities.py` maps every implemented or baseline-available method to its real module and callable symbol. Verification records dependency installation, import success, symbol presence/callability, declared and observed status, offline availability, and product enablement.

`runtime_available=true` means only that an offline callable imports in the current environment. Research methods remain `runtime_enabled=false` unless a separate reviewed product path explicitly promotes them.

## Cross-contract validation

`scripts/validate_repository_contracts.py` checks:

- bidirectional catalog/capability coherence;
- core callable importability;
- catalog counts and version in public documents;
- exact migration head and one matching migration file;
- complete linear Alembic history with no forks, orphans, dependencies, or filename mismatches;
- required evidence, preparation-operation, and task-execution tables;
- canonical benchmark and typed evidence fixtures;
- backend OpenAPI and all frontend binding release contracts;
- isolated catalog import-order invariance.

`scripts/validate_openapi_contracts.py` generates the real FastAPI document and checks API version, required paths, exact methods, authentication, immutable-evidence mutation boundaries, required schemas, and authentication schemes.

`scripts/validate_frontend_openapi_bindings.py` compares handwritten TypeScript clients with generated OpenAPI for top-level fields, enum values, API object and binding names, route fragments, and HTTP methods. Separate contracts cover immutable food evidence, persisted preparation operations, and household plans.

## Executable offline baselines

Current executable or directly evaluable families include:

- TF-IDF and BM25 retrieval;
- popularity and Bayesian-popularity ranking;
- content ranking, item-kNN, matrix factorization, MMR, Bradley-Terry, LinUCB, and Thompson sampling;
- temporal ranking metrics and hard-candidate filtering;
- moving average, seasonal naive, exponential smoothing, Holt, Croston, and TSB forecasting;
- rolling-origin evaluation;
- ridge, Kaplan-Meier, Mahalanobis OOD, and split-conformal baselines;
- deterministic beam, Pareto, optional CP-SAT/MILP, robust-scenario, and exact small-instance planning;
- deterministic preparation scheduling and bounded exact comparison;
- FEFO inventory replay and forecast-to-inventory evaluation.

Executable means callable under the declared dependency and data contract. It does not mean the method is product selected, accurately calibrated, or safe for autonomous decisions.

## Dataset families and acquisition boundaries

Dataset declarations are metadata and acquisition contracts, not bundled data. Before use, every dataset requires:

- license and redistribution review;
- source/version/checksum provenance;
- schema adapter and validation report;
- train/validation/test split policy;
- leakage and duplication review;
- privacy, consent, and geography review where applicable;
- subgroup and coverage reporting;
- documented limitations.

The catalog covers nutrition and recipe sources, food recognition and segmentation, egocentric kitchen video, dietary surveys, sustainability inventories, and synthetic contract fixtures. External acquisition remains disabled until its declared gates are complete.

## Evaluation rules

Every promoted offline result must retain exact dataset/split identity, configuration and dependency lock, random seeds where stochastic, artifact and code commit identity, primary/subgroup/robustness/calibration/hard-violation metrics where applicable, uncertainty where meaningful, baseline comparison, failure examples, and limitations.

Time-dependent tasks require chronological splits. Household and personalization tasks require household isolation. Recipe and ingredient tasks must avoid near-duplicate leakage. Geography, cuisine, device, and source shifts must be evaluated explicitly when relevant.

## Product promotion gates

A research method cannot become product behavior solely because it appears in the catalog or imports successfully. Promotion requires:

1. complete licensed or consented data provenance;
2. representative leakage-safe evaluation;
3. calibration, OOD, subgroup, robustness, and abstention evidence where relevant;
4. privacy and security review;
5. human-review workflow;
6. immutable artifact lineage;
7. rollback and kill-switch design;
8. runtime monitoring and alert thresholds;
9. product authorization and persistence integration;
10. documentation that matches actual readiness.

Clinical, allergy-safety, medication, food-safety, autonomous appliance, and autonomous procurement behavior requires additional external governance and remains disabled.

## Preparation execution and coverage boundary

The Alembic migration chain through `20260802_0018` is the canonical DDL for the product-side append-only task execution ledger. It is not a research inference system:

- task identity and planned timing come from the persisted deterministic schedule;
- events are explicitly entered by authorized household users;
- no presence, appliance, sensor, cooking, temperature, or food-safety state is inferred;
- timing deviations are descriptive operational evidence, not causal labels or quality outcomes;
- coverage metrics report structural state and user-entered event presence, not observed execution quality;
- malformed histories are excluded from task-state denominators and surfaced as warnings;
- task-event data must not be reused for personalization research without a separate consent, privacy, retention, and protocol review.

## Research-only and blocked programs

The following remain research-only or blocked by data/validation unless their declared promotion gates are completed:

- vision and multimodal nutrition estimation;
- constrained recipe generation;
- graph-neural substitution and knowledge-graph recommendation;
- causal and off-policy promotion;
- continual, federated, and privacy-sensitive personalization;
- sustainability claims;
- medical-condition and medication personalization;
- autonomous procurement or appliance control.

## Operational evidence boundary

CI configurations, committed tests, and benchmark scripts are not executed evidence by themselves. The exact hosted workflow run and retained reports for a commit must be inspected before that commit is described as green or benchmark-accepted.
