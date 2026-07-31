# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-01  
**Execution rule:** implement directly on `main` in coherent commits; keep code, tests, migrations, benchmark protocols, capability registry, catalog, documentation, and this roadmap synchronized.

This roadmap includes unfinished work from the original platform plan, newly implemented preparation/forecasting/simulation architecture, and additional high-value models, pipelines, datasets, experiments, and safety controls. Priority does not imply product enablement. High-risk and clinical-risk work remains gated even when code exists.

## Definition of done for every item

An item is not complete merely because a class or endpoint exists. Unless explicitly scoped as research-only, completion requires:

1. validated typed contract;
2. deterministic or seeded behavior;
3. unit and adversarial tests;
4. integration tests across persistence/API/UI where relevant;
5. migrations and rollback constraints where state is persisted;
6. authorization and privacy review;
7. provenance and uncertainty representation;
8. benchmark protocol and acceptance thresholds;
9. capability and catalog registration with truthful readiness;
10. documentation, limitations, and rollback path;
11. no fake fallback, fabricated data, silent relaxation, or request-time promotion.

---

# P0 — Validation, correctness, and operational integrity

## P0.1 Latest-main validation closure

**Goal:** obtain a fully green validation run for the latest `main` revision.

Tasks:

- Inspect direct-push GitHub Actions logs through an authenticated local/CLI path when available.
- Repair Python import, Pytest, Alembic SQLite/PostgreSQL, TypeScript, ESLint, Vitest, Vite, and container failures.
- Verify the planner, forecasting, and inventory replay regression gates.
- Add a workflow summary artifact containing test counts, migration head, benchmark fingerprints, and container digest.
- Add a failure-focused troubleshooting document.

Acceptance:

- All jobs green on one exact commit.
- No skipped required suite.
- Workflow artifacts identify the exact commit and migration revision.

## P0.2 Strict frontend contract audit

Tasks:

- Replace dynamic string-index form updates with typed field descriptors or explicit handlers.
- Enable stricter TypeScript options where currently disabled.
- Verify every API interface against FastAPI OpenAPI output.
- Add generated OpenAPI snapshot and client-contract drift test.
- Remove dormant compatibility APIs after full import-tree proof.

Acceptance:

- `tsc --noEmit` passes independently.
- OpenAPI/client contract test detects renamed, missing, or nullable fields.
- No routed page calls a disabled prototype endpoint.

## P0.3 Preparation evidence versioning hardening

Tasks:

- Add PostgreSQL concurrent registration probe for identical and contradictory profile versions.
- Verify active-reviewed partial unique index on both SQLite and PostgreSQL.
- Make multi-profile imports atomic per input file rather than committing each row independently.
- Add import manifest with file hash, importer version, reviewer identity, and row outcomes.
- Add explicit deactivation/rejection workflow that preserves immutable evidence.

Acceptance:

- Concurrent identical retries produce one version.
- Contradictory same-version content produces a conflict.
- New reviewed version supersedes exactly one prior active review.
- Failed batch imports leave no partial committed set unless explicitly requested.

## P0.4 Inventory and reservation property testing

Tasks:

- Add Hypothesis tests for quantity intervals, version transitions, idempotency fingerprints, and unit incompatibility.
- Generate competing reservation/commit/release schedules.
- Verify conservation laws: initial + purchases − consumption − discard = ending inventory, within explicit interval semantics.
- Add transaction rollback tests after simulated failures.

Acceptance:

- No generated sequence produces negative stock, double consumption, duplicate event effects, or overbooking.

## P0.5 Security and privacy baseline

Tasks:

- Add token revocation/refresh strategy.
- Add verified email and password reset.
- Add rate limiting for auth and invitation endpoints.
- Add secure headers, request-size limits, and dependency vulnerability scanning without automated PR creation.
- Add export/delete workflow and retention policy.
- Threat-model invitation tokens, household access, user data paths, artifact registry, offline experiment configs, and uploaded evidence.

Acceptance:

- Security tests cover brute-force controls, token misuse, object authorization, and data lifecycle.

---

# P1 — Complete the household food operations platform

## P1.1 Integrated plan → occurrence → preparation pipeline

Current state: reviewed profiles compile to tasks; integrated scheduling endpoint exists.

Remaining tasks:

- Generate candidate occurrences from persisted household plans with explicit meal deadline and serving review.
- Never auto-accept generated occurrences; require user confirmation.
- Add integrated frontend control for fail-closed compile-and-schedule.
- Display unresolved recipes, serving-range gaps, source versions, and content hashes before scheduling.
- Persist approved preparation schedules with source plan/version and resource calendar version.
- Invalidate/rebuild schedules when plan, serving count, profile version, or resource availability changes.

Acceptance:

- Every scheduled plan task is traceable to a plan meal and immutable reviewed profile.
- Any unresolved occurrence blocks default scheduling.

## P1.2 Preparation resource calendars

Models/features:

- Persisted household resources.
- Resource availability recurrence rules.
- Human labor resources and per-person availability.
- Active-work versus passive-wait intervals.
- Handoff and supervision requirements.
- Setup/cleanup transition times.
- Optional exact RCPSP/CP-SAT benchmark.

Acceptance:

- Scheduler distinguishes appliance capacity from active human labor.
- No unattended-cooking assumption is inferred.
- Deterministic heuristic is compared against exact small-fixture optimum.

## P1.3 Joint meal and schedule repair

Architectures:

- Two-stage decomposition: meal plan then schedule repair.
- Benders-style feasibility cuts from schedule back to planner.
- Joint CP-SAT benchmark for small horizons.
- Local-search repair after pantry/resource changes.

Metrics:

- plan objective regret;
- preparation feasibility;
- makespan;
- active labor;
- resource utilization;
- hard violation count;
- number of changed meals after repair.

Acceptance:

- Infeasible schedules return actionable meal substitutions or timing changes without relaxing allergies or reviewed evidence.

## P1.4 Conversion and food-evidence history

Tasks:

- Immutable versioned ingredient conversion records.
- Immutable versioned storage policy records.
- Content hashes and supersession links.
- One active reviewed record per natural evidence key.
- Review/deactivation CLI and UI.
- Coverage and stale-review dashboards.

Acceptance:

- No reviewed evidence is overwritten in place.
- Every automatic conversion identifies the exact evidence version and uncertainty interval.

## P1.5 Pantry/leftover operational UX

Tasks:

- Lot split/merge.
- Bulk purchase/import.
- Recall/quarantine state.
- Barcode/receipt adapter with human confirmation.
- Expiry and reservation timeline.
- Inventory reconciliation report.
- Offline conflict handling.
- Export/import with idempotency manifest.

Acceptance:

- Every mutation remains ledgered, authorized, versioned, and retry safe.

---

# P1 — Forecasting, inventory simulation, and procurement evaluation

## P1.6 Forecast benchmark expansion

Implemented baselines:

- moving average;
- seasonal naive;
- simple exponential smoothing;
- damped Holt trend;
- Croston;
- TSB;
- rolling-origin evaluation.

Next baselines:

- naïve last-value and drift baselines;
- SBA-corrected Croston;
- ADIDA and IMAPA intermittent aggregation;
- Theta method;
- ARIMA/ETS through optional research dependencies;
- quantile regression;
- conformalized forecast intervals;
- hierarchical forecast reconciliation across ingredient/category/household levels;
- N-BEATS/N-HiTS/TFT only after sufficient temporal data.

Datasets/fixtures:

- synthetic seasonal/intermittent series;
- consented household inventory event histories;
- optional external retail-demand benchmark adapters after license review.

Experiments:

- rolling-origin horizon matrix;
- intermittent-demand strata;
- cold-start history length;
- demand-shift stress;
- calibration/coverage;
- subgroup performance by ingredient frequency and shelf life.

Acceptance:

- Every model compared on identical origins.
- Point and interval metrics reported.
- No model is selected solely on one synthetic seed.

## P1.7 Forecast-to-inventory closed-loop replay

Pipeline:

1. Temporal split of historical demand.
2. Forecast demand distribution/interval.
3. Translate forecast into explicit reorder policy.
4. Replay FEFO perishable inventory.
5. Measure stockout, waste, service level, orders, holding, and cost.
6. Compare policies under common demand paths.

Policies:

- reorder point/order-up-to;
- periodic review;
- newsvendor quantiles;
- shelf-life-aware base stock;
- robust policy over forecast intervals;
- no-order baseline.

Acceptance:

- Forecast accuracy and operational outcomes reported separately.
- Better MAE is never assumed to imply lower waste or stockout.

## P1.8 Perishable inventory simulator expansion

Current baseline:

- deterministic FEFO replay;
- expiry-before-demand semantics;
- explicit positive lead time;
- reorder-point/order-up-to policy;
- stockout, waste, fill rate, demand service level, average inventory, and event ledger.

Next features:

- pending-order and pipeline inventory metrics;
- variable supplier lead times;
- partial delivery and cancellation;
- batch-specific purchase cost;
- holding, ordering, stockout, and waste costs;
- substitution between compatible SKUs using reviewed conversion/substitution evidence;
- storage-capacity constraints;
- multi-echelon pantry/store simulation;
- stochastic scenario replication with seeded common random numbers;
- policy-grid and Bayesian optimization offline benchmark;
- conservation-law audit and event replay verifier.

Acceptance:

- Simulator remains non-mutating.
- Every stochastic run records seed and scenario fingerprint.
- Policy comparison uses common demand/lead-time scenarios.

---

# P1 — Recommendation and preference evaluation

## P1.9 Ranking benchmark protocol

Implemented baselines:

- popularity;
- Bayesian-smoothed popularity;
- content preference;
- item-kNN;
- matrix factorization;
- MMR diversification.

Next:

- user-kNN;
- implicit ALS/BPR optional baselines;
- calibrated popularity by recency;
- two-tower retrieval;
- LightGCN;
- sequential SASRec/BERT4Rec;
- slate reranking with nutrition/taste/diversity constraints;
- uncertainty-aware abstention;
- cold-start metadata encoder.

Metrics:

- Recall/NDCG/MAP/HitRate;
- coverage and novelty;
- intra-list diversity;
- calibration to declared preferences;
- repeat/cuisine/ingredient exposure;
- hard restriction violation count;
- temporal/user-group splits;
- popularity and cold-start strata.

Acceptance:

- Hard allergies/restrictions applied before ranking.
- Ranking diversity cannot reintroduce filtered items.
- User-level split prevents leakage.

## P1.10 Consent-based preference data workflow

Tasks:

- Explicit consent and purpose selection.
- Append-only pairwise and outcome feedback.
- Data minimization and retention period.
- Offline-only training export.
- Delete/export propagation into experiment datasets and artifacts.
- No request-time online updates.

Acceptance:

- Every training record is traceable to consent state and dataset version.

---

# P2 — Robustness, uncertainty, and optimization research

## P2.1 Robust planning scenario library

Scenario dimensions:

- ingredient quantity uncertainty;
- conversion multiplier intervals;
- price changes;
- pantry uncertainty;
- serving-count variation;
- recipe nutrition uncertainty;
- unavailable appliance windows;
- preparation duration intervals;
- member attendance changes.

Methods:

- worst-case enumeration for small fixtures;
- scenario optimization;
- chance constraints;
- distributionally robust optimization;
- CVaR objectives;
- sensitivity and counterfactual explanations.

Acceptance:

- Scenario definitions are versioned and hashed.
- Hard allergy constraints remain invariant in every scenario.
- Robust objective and nominal regret are both reported.

## P2.2 Uncertainty propagation pipeline

Tasks:

- Interval arithmetic for quantities and conversions.
- Monte Carlo propagation with deterministic seeds.
- Correlation assumptions represented explicitly.
- Nutrition and shopping intervals.
- Conformal forecast intervals.
- Plan feasibility probability and abstention criteria.

Acceptance:

- No uncertainty interval is collapsed to a point without disclosure.
- Coverage evaluated on held-out data where ground truth exists.

## P2.3 Multiobjective optimization expansion

Methods:

- ε-constraint Pareto generation;
- NSGA-II research baseline;
- lexicographic priorities;
- reference-point interactive search;
- hypervolume and epsilon indicator;
- fairness-aware household objectives;
- minimax member dissatisfaction;
- active preference elicitation.

Acceptance:

- Product defaults remain deterministic and disclosed.
- No safety constraint is converted to a soft preference.

## P2.4 Exact preparation scheduling benchmark

Methods:

- RCPSP CP-SAT;
- MILP time-indexed scheduling;
- cumulative resource constraints;
- precedence and deadline constraints;
- optional setup times;
- active labor versus passive appliances.

Acceptance:

- Heuristic optimality gap measured on canonical small fixtures.
- Exact solver dependency absence is explicit.

---

# P2 — Research infrastructure and evaluation governance

## P2.5 Catalog and capability synchronization

Tasks:

- Generate catalog counts in docs automatically.
- Validate every implemented/baseline catalog model has a callable registration.
- Validate every registered callable has a catalog model.
- Validate source paths and optional dependencies.
- Add deprecation/supersession fields to catalog entries.
- Add readiness transition audit log.

Acceptance:

- CI fails on registry/catalog/documentation drift.

## P2.6 Experiment runner expansion

Tasks:

- Add whitelisted implementations for new forecast/ranking/simulation baselines.
- Typed experiment-specific configs.
- Multi-seed repeats.
- Resume/checkpoint manifests.
- Resource/time budgets.
- Dataset fingerprint verification before and after runs.
- Metrics/artifact persistence in `experiment_runs`.
- Comparison reports and confidence intervals.

Acceptance:

- Arbitrary code cannot be supplied through API/config.
- Every result records code commit, environment, seed, dataset hash, and model hash.

## P2.7 Dataset registry and adapters

Potential adapters, subject to license/consent review:

- retail/food demand time-series benchmarks;
- recipe interaction datasets;
- grocery basket datasets;
- appliance/preparation-time evidence sources;
- Open Food Facts quality/allergen records;
- additional national nutrient databases;
- lifecycle assessment sources.

For each adapter:

- license and allowed-use record;
- source version and retrieval hash;
- schema card;
- missingness/quality report;
- privacy/consent status;
- leakage-safe split contract;
- manual enablement only.

## P2.8 Mutation, fuzz, and metamorphic testing

Targets:

- quantity parser and conversions;
- optimizer invariants;
- scheduler dependencies/capacity;
- evidence import/versioning;
- inventory simulation conservation;
- API authorization;
- migrations;
- catalog reference validation.

Metamorphic properties:

- input reordering does not change deterministic output;
- increasing capacity cannot make an already scheduled task infeasible absent another changed constraint;
- adding stock cannot increase stockout under the same policy/demand;
- identical idempotent retry does not change state;
- stricter budget cannot create a cheaper infeasible selection;
- superseded evidence remains readable but not active.

---

# P3 — Vision, multimodal, language, graph, and generation research

These are high-cost research programs, not near-term product features.

## P3.1 Food vision stack

Architectures:

- ResNet/ConvNeXt/ViT/Swin classification;
- DINOv2 linear/probe baselines;
- Faster R-CNN/DETR-style detection;
- U-Net/DeepLab/SegFormer/Mask2Former segmentation;
- promptable segmentation baseline;
- RGB-D portion estimation;
- component-level weight prediction;
- ensembles and OOD detection.

Pipelines:

- food/non-food gate;
- multi-item detection/segmentation;
- component identity;
- portion/weight uncertainty;
- nutrient lookup with provenance;
- abstention and human correction.

Gates:

- license;
- OOD;
- calibration;
- subgroup/geographic cuisine coverage;
- uncertainty coverage;
- false-confidence review;
- clinical validation before nutrition claims.

## P3.2 Ingredient and instruction understanding

Methods:

- ingredient NER and quantity/unit normalization;
- ontology linking;
- instruction event extraction;
- tool/appliance extraction;
- dependency DAG induction;
- duration interval extraction with provenance;
- human-reviewed preparation-profile generation assistant.

Rules:

- extracted values remain external-unverified until reviewed;
- no automatic promotion to reviewed evidence.

## P3.3 Substitution graph and constrained generation

Methods:

- reviewed substitution knowledge graph;
- graph embeddings/GraphSAGE;
- constraint-aware ranking;
- retrieval-augmented generation;
- constrained decoding;
- verifier and rejection layer.

Hard gates:

- allergy false-negative review;
- dietary compatibility;
- preparation-function compatibility;
- quantity/conversion evidence;
- human approval.

## P3.4 Multimodal recipe retrieval

Methods:

- CLIP/SigLIP baseline;
- cross-modal reranking;
- ingredient-aware embeddings;
- hard-negative mining;
- multilingual retrieval.

Metrics:

- Recall@K and median rank;
- cuisine/subgroup coverage;
- OOD retrieval;
- duplicate leakage.

---

# P3 — Personalization, continual learning, causal, and privacy research

## P3.5 Safe offline policy evaluation

Methods:

- IPS/SNIPS;
- doubly robust estimators;
- support-overlap diagnostics;
- conservative policy improvement;
- constrained contextual bandits;
- replay simulation.

No product bandit is enabled until:

- consented logging policy is known;
- propensity scores are valid;
- action support is adequate;
- safety constraints are invariant;
- kill switch and rollback exist;
- human review approves deployment.

## P3.6 Continual personalization

Architectures:

- replay buffers;
- regularization/adapters;
- per-user lightweight models;
- temporal drift detection;
- explicit reset/delete propagation.

Metrics:

- forgetting;
- forward/backward transfer;
- calibration over time;
- subgroup drift;
- privacy leakage;
- deletion compliance.

Request-time online model mutation remains prohibited.

## P3.7 N-of-1 and causal research

Methods:

- Bayesian N-of-1 simulation;
- interrupted time-series;
- propensity adjustment;
- sensitivity analyses;
- negative controls.

Blocked until:

- consented longitudinal data;
- preregistered protocol;
- confounder and adherence measurement;
- clinical review;
- external validation;
- explicit non-diagnostic user communication.

## P3.8 Privacy and federated research

Experiments:

- membership inference;
- attribute inference;
- model inversion;
- gradient leakage;
- differential privacy accounting;
- federated simulation;
- secure aggregation feasibility.

No privacy claim may be made from the presence of a technique alone.

---

# P3 — Sustainability research

Tasks:

- geography-aware LCA mapping;
- production-method and transport provenance;
- functional-unit normalization;
- uncertainty intervals and Monte Carlo propagation;
- AGRIBALYSE/ecoinvent/water-footprint adapters;
- ingredient-to-LCA entity resolution;
- scenario comparison rather than single-point labels.

Blocked product behavior:

- no authoritative sustainability score without source, geography, production method, uncertainty, and date.

---

# Documentation and status synchronization checklist

Every substantive implementation commit must consider updates to:

- `README.md`;
- `docs/IMPLEMENTATION_STATUS.md`;
- `docs/ROADMAP.md`;
- `docs/RESEARCH_PLATFORM.md`;
- domain-specific docs;
- Alembic head and schema verification;
- capability registry;
- research catalog;
- tests and benchmark fixtures;
- CI validation commands.

## Next direct-main implementation order

1. Close latest-main validation failures.
2. Fix strict TypeScript preparation form typing.
3. Add integrated compile-and-schedule frontend control.
4. Make preparation profile batch imports atomic and concurrency-tested.
5. Register/catalog the FEFO inventory simulator after benchmark review.
6. Implement forecast-to-inventory closed-loop benchmark.
7. Add exact small-fixture preparation scheduling comparator.
8. Version conversion and storage-policy evidence.
9. Add Playwright accessibility/authenticated household flows.
10. Continue advanced research only through explicit data, evaluation, artifact, promotion, and rollback gates.
