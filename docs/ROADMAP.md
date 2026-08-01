# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-01  
**Execution rule:** implement directly on `main` in coherent commits. Keep code,
tests, migrations, benchmark fixtures, capability registrations, catalog
records, public status documents, and this roadmap synchronized.

Current platform contract:

- database migration head `20260801_0007`;
- effective catalog `2026-08-01.3`;
- 37 task contracts;
- 30 dataset families;
- 75 model/algorithm families;
- 29 experiment contracts;
- 39 feature contracts.

A class, endpoint, fixture, synthetic benchmark, or catalog entry is not done
unless its scope is explicit. Product work requires authorization,
persistence, UX, tests, operations, and rollback. Offline research requires
typed data contracts, leakage-safe evaluation, deterministic or seeded replay,
metrics, limitations, and truthful non-enablement.

## Definition of done

Unless an item is explicitly research-only, completion requires:

1. validated typed contract;
2. deterministic or seeded behavior;
3. unit, adversarial, and failure-path tests;
4. persistence, API, and UI integration where applicable;
5. migration and rollback constraints for stored state;
6. authorization, privacy, and abuse review;
7. provenance and uncertainty representation;
8. benchmark protocol and acceptance thresholds;
9. catalog/capability registration with truthful readiness;
10. documentation, limitations, and rollback path;
11. no fabricated fallback, silent relaxation, or automatic promotion.

# Completed architecture milestones

## C1 — Transactional household platform

Completed:

- secure authentication and profile-completeness boundary;
- owner/editor/viewer households;
- hashed invitations and retry-safe acceptance;
- transactional pantry lots and leftovers;
- append-only inventory ledger;
- reservations and cross-plan overbooking protection;
- optimistic versions;
- atomic full-request idempotency fingerprints;
- PostgreSQL inventory, reservation, and request-idempotency probes;
- evidence-driven TypeScript household workspace.

## C2 — Quantity-aware household planning

Completed:

- horizon-level beam planner;
- hard allergy and dietary filtering;
- household target aggregation;
- pantry-aware household objective;
- persisted plan provenance and diagnostics;
- shopping reconciliation and batch grouping;
- Pareto, optional CP-SAT/MILP, robust scenarios, and planner benchmark gate.

## C3 — Immutable preparation evidence

Completed:

- separate immutable recipe preparation profiles;
- profile versions, hashes, source/reviewer metadata, and supersession;
- reviewed serving ranges;
- task-template DAGs and duration intervals;
- one active reviewed profile per recipe;
- atomic batch registration;
- identical, contradictory, and successor race handling;
- integrity-checked import manifests;
- offline importer and read/compile APIs;
- PostgreSQL evidence concurrency probe.

## C4 — Preparation scheduling

Completed:

- deterministic dependency-aware product scheduler;
- cumulative resource capacity;
- availability windows and deadlines;
- downstream blocked-task diagnostics;
- critical-path and utilization diagnostics;
- fail-closed compile-and-schedule pipeline;
- separate manual and immutable-evidence frontend workflows;
- exact bounded branch-and-bound comparator;
- canonical exact fixture and zero-gap CI gate.

## C5 — Forecasting and inventory evaluation

Completed:

- moving average, seasonal naive, SES, damped Holt, Croston, and TSB;
- rolling-origin forecast evaluation;
- FEFO perishable inventory replay;
- stockout, fill-rate, waste, service, inventory, and event metrics;
- forecast-to-inventory closed-loop evaluation;
- canonical fixtures and direct-main gates.

## C6 — Ranking evaluation

Completed:

- popularity, Bayesian popularity, content, item-kNN, matrix factorization,
  and MMR;
- seeded synthetic ranking fixture;
- temporal leave-last-out split;
- common unseen and hard-allowed candidate sets;
- hard-exclusion audit;
- Recall, HitRate, MRR, NDCG, coverage, novelty, diversity, and group metrics;
- separate accuracy, diversity, and coverage leaders;
- direct-main hard-violation gate.

## C7 — Immutable conversion and storage evidence

Completed:

- immutable ingredient-conversion versions;
- immutable storage-policy versions;
- UTC-normalized review metadata;
- content hashes and supersession chains;
- one active reviewed record per natural key;
- PostgreSQL advisory locking for first-version and successor races;
- conservative legacy migration;
- immutable official-policy seeding;
- exact reviewed conversion application;
- atomic leftover-to-policy-version linkage;
- policy ID/version/hash in the event ledger;
- migration, service, API, and concurrency tests.

## C8 — Governed research infrastructure

Completed:

- validated catalog with readiness, risk, and reference checks;
- additive catalog extension and reconstruction tests;
- mechanically verified callable registry;
- cards, splits, metrics, drift, manifests, and experiment-run state;
- cross-process artifact registry and promotion stages;
- repository cross-contract validator;
- direct-main validation spanning backend, benchmarks, migrations,
  concurrency, frontend, container, and retained reports.

# P0 — Immediate correctness and validation closure

## P0.1 Inspect and close the latest complete workflow

Tasks:

- identify the exact latest `main` commit and its Actions run;
- inspect backend, migration, PostgreSQL, frontend, and container logs;
- repair every observed failure without weakening a required gate;
- retain reports containing commit SHA, migration head, catalog version,
  benchmark fingerprints, test counts, and container digest;
- document failure triage and rerun procedures.

Acceptance:

- every required job is green on one exact commit;
- no required suite is skipped or weakened;
- no statement claims green status without the inspected run.

## P0.2 Repository-contract hardening

Tasks:

- add a direct unit test for `validate_repository_contracts()`;
- validate benchmark schemas, not only JSON-object shape;
- validate the complete Alembic revision chain and single head;
- generate public count/version blocks from one canonical metadata source;
- verify catalog extension import order in isolated Python processes;
- retain the contract report as a workflow artifact.

Acceptance:

- catalog, capabilities, docs, migration head, required tables, and fixtures
  cannot drift without CI failure.

## P0.3 Strict frontend/OpenAPI closure

Tasks:

- generate FastAPI OpenAPI JSON in CI;
- snapshot API paths and response schemas;
- validate frontend interfaces against generated schemas;
- enable stricter TypeScript options incrementally;
- eliminate compatibility exports only after import-tree proof;
- add nullability, enum, and `204/205` drift tests.

Acceptance:

- renamed, removed, or newly nullable backend fields fail frontend contract
  validation before release.

## P0.4 Property and metamorphic testing

Targets:

- ingredient parser and conversions;
- inventory intervals and conservation;
- reservations and idempotency;
- preparation DAG, capacity, and evidence versions;
- immutable conversion and storage histories;
- exact scheduler and heuristic comparison;
- inventory replay and closed loop;
- ranking filters and temporal leakage;
- migrations and catalog references.

Properties:

- deterministic input reordering does not change output;
- increasing resource capacity cannot invalidate an already feasible schedule;
- adding usable stock cannot increase stockout under the same demand path;
- identical idempotent retries cannot change state;
- hard exclusions can only remove ranking candidates;
- superseded evidence remains readable but not active;
- one natural evidence key has at most one active reviewed version;
- immutable leftover links do not change when the active policy later changes.

# P1 — Complete immutable evidence operations

## P1.1 Reviewed conversion import manifests

Add:

- source file SHA-256;
- importer protocol/version and repository commit;
- operator and reviewer identities;
- complete natural keys and content hashes;
- non-mutating database preflight;
- atomic all-or-nothing registration;
- per-row action/outcome records;
- durable pre-apply manifest;
- honest post-commit manifest-write failure state;
- PostgreSQL concurrent import probe.

Acceptance:

- every imported version set is traceable to one file hash and one transaction.

## P1.2 Reviewed storage-policy import and lifecycle

Add equivalent manifest-driven operations for storage policies:

- register reviewed versions;
- reject/deactivate a version while preserving history;
- supersede through a new reviewed version;
- require operator/reviewer identities;
- attach source-document metadata and optional signatures;
- prohibit mutation of content after registration.

## P1.3 Evidence coverage dashboard

Metrics:

- preparation profile coverage by recipe and serving range;
- conversion coverage by ingredient and unit direction;
- storage-policy coverage by category and storage state;
- review age and stale-evidence counts;
- unreviewed, legacy, contradictory, and inactive records;
- automatic-operation coverage versus abstention rate;
- leftovers linked to exact immutable versions.

## P1.4 Frontend immutable evidence migration

Tasks:

- move research evidence views to history endpoints;
- show record/policy versions, content hashes, reviewer, review time, and
  supersession state;
- show exact policy provenance beside every leftover;
- preserve the legacy compatibility surface only until all consumers migrate;
- add browser tests for exact provenance and inactive-version history.

# P1 — Complete preparation operations

## P1.5 Persist household resource calendars and schedules

Models:

- household resource and immutable calendar version;
- availability windows and recurrence rules;
- person-specific labor resources;
- approved schedule with source plan/profile/resource versions;
- status: draft, approved, invalidated, completed, cancelled;
- append-only schedule event ledger.

Rules:

- changing the plan, servings, evidence version, or resource calendar
  invalidates dependent schedules;
- approval is explicit;
- no background execution or appliance control.

## P1.6 Plan-to-occurrence generation

Tasks:

- derive candidate meal occurrences from persisted plan meals;
- require explicit serving count and finish-time review;
- surface recipes without reviewed profiles;
- show profile version/hash before approval;
- never auto-submit generated occurrences;
- persist the confirmed occurrence set with the plan version.

## P1.7 Active labor, passive time, supervision, and transitions

Extend task evidence with:

- active labor interval versus passive wait;
- supervision requirement;
- unattended-allowed state;
- setup and cleanup durations;
- setup family and resource transition;
- handoff prerequisites;
- multi-person availability.

Research comparators:

- RCPSP CP-SAT;
- time-indexed MILP;
- active-labor heuristic;
- setup-aware local search.

## P1.8 Joint plan and schedule repair

Architectures:

- two-stage plan then schedule repair;
- schedule infeasibility cuts back to meal selection;
- small-horizon joint CP-SAT benchmark;
- local repair after pantry/resource changes;
- minimal-change objective.

Metrics:

- plan regret;
- preparation feasibility;
- makespan and active labor;
- changed-meal count;
- hard violation count;
- user-confirmed repair acceptance.

# P1 — Forecasting and inventory policy expansion

## P1.9 Forecast baselines and uncertainty

Add:

- last-value and drift baselines;
- SBA Croston correction;
- ADIDA and IMAPA;
- Theta method;
- optional ARIMA/ETS;
- quantile regression;
- split-conformal forecast intervals;
- hierarchical reconciliation;
- N-BEATS, N-HiTS, or TFT only after sufficient temporal data.

Experiments:

- history-length and cold-start strata;
- intermittent-demand strata;
- horizon matrix;
- demand-shift stress;
- interval coverage/width;
- subgroup performance by frequency and shelf life.

## P1.10 Inventory costs and stochastic scenarios

Add:

- pending-order and pipeline inventory metrics;
- variable lead times;
- partial delivery and cancellation;
- purchase, holding, ordering, stockout, and waste costs;
- storage capacity;
- reviewed substitution between compatible SKUs;
- multi-echelon pantry/store simulation;
- seeded common random numbers;
- conservation-law verifier;
- replay of event ledger back to state.

Policies:

- no-order baseline;
- periodic review;
- newsvendor quantile;
- shelf-life-aware base stock;
- robust interval policy;
- explicit cost trade-off frontier.

## P1.11 Closed-loop forecast/policy benchmark

Require:

- common realized demand and lead-time paths;
- forecast metrics separate from operational metrics;
- policy hyperparameters declared and hashed;
- multi-seed confidence intervals;
- no automatic procurement model selection;
- human-reviewed candidate promotion only.

# P1 — Recommendation and preference platform

## P1.12 Real-data ranking protocol

Data requirements:

- explicit consent and purpose;
- event timestamps and item availability;
- known logging and serving mechanism;
- deletion/export propagation;
- minimum-history and cold-start strata;
- user-level temporal splits;
- duplicate and near-duplicate audit.

Potential models:

- user-kNN;
- implicit ALS/BPR;
- recency-calibrated popularity;
- two-tower retrieval;
- LightGCN;
- SASRec/BERT4Rec;
- slate reranking with hard restrictions;
- uncertainty-aware abstention;
- cold-start metadata encoder.

## P1.13 Consent-based preference workflow

Tasks:

- explicit consent and purpose selector;
- append-only pairwise and outcome events;
- data minimization and retention period;
- offline training export;
- deletion propagation to datasets and artifacts;
- no request-time online updates.

# P2 — Robust planning and uncertainty

## P2.1 Scenario library

Version and hash scenarios for quantities, conversion uncertainty, prices,
pantry uncertainty, servings, nutrition evidence, appliance windows,
preparation durations, and member attendance.

Methods:

- worst case;
- scenario optimization;
- chance constraints;
- distributionally robust optimization;
- CVaR;
- sensitivity and counterfactual explanations.

## P2.2 Uncertainty propagation

- interval arithmetic;
- seeded Monte Carlo;
- explicit correlation assumptions;
- nutrition and shopping intervals;
- forecast intervals;
- plan-feasibility probability;
- abstention criteria.

## P2.3 Multiobjective expansion

- epsilon-constraint Pareto generation;
- NSGA-II;
- lexicographic priorities;
- reference-point interaction;
- hypervolume and epsilon indicators;
- minimax member dissatisfaction;
- active preference elicitation.

Hard safety constraints must never become soft objectives.

# P2 — Research infrastructure

## P2.4 Experiment runner

- typed experiment-specific configurations;
- whitelist ranking, forecast, simulation, and exact-scheduler callables;
- multi-seed repeats;
- resume/checkpoint manifests;
- resource and time budgets;
- dataset hash verification;
- persisted metrics and artifacts;
- confidence intervals and comparison reports.

## P2.5 Dataset registry and adapters

Potential sources, subject to license and consent review:

- retail/food demand time-series benchmarks;
- recipe interaction datasets;
- grocery basket datasets;
- preparation-time evidence sources;
- Open Food Facts quality/allergen data;
- additional national nutrient databases;
- lifecycle-assessment datasets.

Every adapter requires source/version/hash, license, schema card, quality report,
privacy state, split contract, and explicit enablement.

## P2.6 Release artifacts and observability

- retain benchmark reports as workflow/release artifacts;
- record exact commit and environment;
- expose experiment comparison UI;
- add representative latency and memory budgets;
- distinguish process health, dependency readiness, and evidence readiness.

# P3 — Gated high-cost research

## P3.1 Vision and multimodal nutrition

Potential architectures:

- ResNet, ConvNeXt, ViT, Swin, and DINOv2 classification;
- Faster R-CNN or DETR detection;
- U-Net, DeepLab, SegFormer, and Mask2Former segmentation;
- RGB-D portion estimation;
- component weight prediction;
- ensembles and OOD detection.

Required gates include license, cuisine/geography coverage, OOD, calibration,
subgroup evaluation, uncertainty coverage, human correction, and clinical
validation before nutrition claims.

## P3.2 Ingredient and instruction understanding

- ingredient NER and ontology linking;
- instruction events, tools, appliances, dependencies, and duration intervals;
- provenance-bearing extraction assistant;
- extracted records remain external-unverified until human review.

## P3.3 Substitution and constrained generation

- reviewed substitution knowledge graph;
- graph embeddings or GraphSAGE;
- constraint-aware ranking;
- retrieval-augmented constrained generation;
- verifier and rejection layer.

Hard gates: allergen false-negative review, dietary compatibility, functional
compatibility, conversion evidence, and human approval.

## P3.4 Safe offline policy evaluation

- IPS and SNIPS;
- doubly robust estimators;
- overlap diagnostics;
- conservative policy improvement;
- constrained contextual bandits;
- replay simulation.

No product bandit until propensities, support, consent, safety constraints,
kill switch, rollback, and human approval exist.

## P3.5 Continual personalization

- replay buffers;
- adapters or per-user lightweight models;
- drift and reset/delete propagation;
- forgetting, transfer, calibration, subgroup, privacy, and deletion metrics.

Request-time online mutation remains prohibited.

## P3.6 N-of-1, causal, privacy, and federated research

- Bayesian N-of-1 simulation;
- interrupted time series and sensitivity analyses;
- membership and attribute inference, inversion, and gradient leakage;
- differential privacy accounting;
- federated simulation and secure aggregation feasibility.

These remain blocked by consent, longitudinal measurement, preregistration,
clinical review, privacy review, and external validation.

## P3.7 Sustainability

- geography-aware LCA mapping;
- production and transport provenance;
- functional-unit normalization;
- uncertainty intervals;
- AGRIBALYSE, ecoinvent, and water-footprint adapters;
- ingredient entity resolution;
- scenario comparison instead of one authoritative score.

# Documentation synchronization checklist

Every substantive implementation commit must consider updates to:

- `README.md`;
- `docs/IMPLEMENTATION_STATUS.md`;
- `docs/ROADMAP.md`;
- `docs/RESEARCH_PLATFORM.md`;
- relevant domain documents;
- Alembic head and schema verifier;
- capability registry;
- effective research catalog;
- tests and benchmark fixtures;
- CI commands and repository-contract validator.

# Next direct-main implementation order

1. inspect and close the latest complete workflow;
2. add direct repository-contract regression and fixture schema validation;
3. add immutable conversion and storage import/deactivation manifests;
4. expose exact leftover policy provenance in the frontend;
5. persist household resource calendars and approved schedules;
6. add OpenAPI/frontend drift validation;
7. add Playwright and axe authenticated flows;
8. expand inventory costs and stochastic closed-loop policies;
9. add real-data consent and ranking workflows;
10. continue high-risk research only through explicit data, evaluation,
    artifact, approval, rollback, and monitoring gates.
