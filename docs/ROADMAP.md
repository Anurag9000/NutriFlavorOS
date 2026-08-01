# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-01  
**Execution rule:** implement directly on `main` in coherent commits. Keep code,
tests, migrations, benchmark fixtures, capability registrations, catalog
records, CI, public status documents, and this roadmap synchronized.

Current platform contract:

- database migration head `20260801_0008`;
- OpenAPI release contract `2026-08-01.2`;
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
3. unit, adversarial, concurrency, and failure-path tests where applicable;
4. persistence, API, and UI integration where applicable;
5. migration and rollback constraints for stored state;
6. authorization, privacy, and abuse review;
7. provenance and uncertainty representation;
8. benchmark or operational acceptance criteria;
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
- generated OpenAPI path/schema/authentication validator;
- direct-main validation spanning backend, benchmarks, migrations,
  concurrency, frontend, container, and retained reports.

## C9 — Manifest-driven immutable food evidence

Completed:

- typed joint conversion/storage import document;
- source-file and content hashing;
- reviewer/operator identity retention;
- non-mutating database preflight;
- deterministic lock ordering;
- one all-or-nothing transaction;
- idempotent reapplication;
- contradictory version rejection;
- exact active and inactive predecessor lineage;
- durable pending/final/failure manifests;
- honest already-committed manifest failure states;
- canonical CI fixture and dry-run/apply/reapply sequence.

## C10 — Append-only evidence lifecycle

Completed:

- migration `20260801_0008`;
- append-only exact-target lifecycle ledger;
- deactivation and rejection actions;
- actor, reason, metadata, idempotency key, request fingerprint, and prior state;
- atomic multi-action documents;
- actor/operator matching;
- retry collapse and contradictory-key rejection;
- invalid-target rollback;
- corrected successor lineage after withdrawal;
- read-only authenticated lifecycle history;
- lifecycle API mutation prohibition through OpenAPI contract;
- canonical lifecycle fixture and dry-run/apply/reapply CI sequence;
- PostgreSQL identical retry, contradictory reuse, and withdrawal/successor
  race probes.

# P0 — Immediate correctness and validation closure

## P0.1 Inspect and close one exact complete workflow

Tasks:

- identify the exact latest `main` commit and its Actions run;
- inspect backend, migration, PostgreSQL, frontend, and container logs;
- repair every observed failure without weakening a required gate;
- inspect retained reports and commit identity;
- document failure-triage and rerun procedures.

Acceptance:

- every required job is green on one exact commit;
- no required suite is skipped or weakened;
- no statement claims green status without the inspected run.

## P0.2 Repository-contract hardening

Completed:

- direct regression for `validate_repository_contracts()`;
- exact migration-head and matching-file checks;
- immutable table requirements;
- catalog/capability bidirectional checks;
- public count/version checks;
- typed food-evidence import fixture;
- typed lifecycle fixture;
- retained contract report.

Remaining:

- validate every benchmark through an explicit Pydantic/JSON schema rather than
  only script-level parsing;
- validate the complete Alembic revision chain and detect internal forks;
- generate public metadata blocks from one canonical source;
- verify catalog extension import order in isolated Python processes.

## P0.3 Strict frontend/OpenAPI closure

Completed:

- generated FastAPI OpenAPI validation in CI;
- required path and exact-method checks;
- authenticated-operation checks;
- immutable-evidence mutation-boundary checks;
- required provenance and lifecycle schema fields;
- OpenAPI release contract `2026-08-01.2`.

Remaining:

- generate frontend types from OpenAPI or validate handwritten interfaces
  mechanically against it;
- enable stricter TypeScript options incrementally;
- eliminate compatibility exports after import-tree proof;
- add explicit nullability, enum, `204`, and `205` transport drift tests.

## P0.4 Property and metamorphic testing

Targets:

- ingredient parser and conversions;
- inventory intervals and conservation;
- reservations and idempotency;
- preparation DAG, capacity, and evidence versions;
- immutable conversion/storage histories and lifecycle;
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
- superseded or withdrawn evidence remains readable but not active;
- one natural evidence key has at most one active reviewed version;
- immutable leftover links do not change when active policy state changes;
- lifecycle events never rewrite content hashes or source provenance.

# P1 — Product evidence completion

## P1.1 Evidence coverage dashboard

Metrics:

- preparation profile coverage by recipe and serving range;
- conversion coverage by ingredient and unit direction;
- storage-policy coverage by category and storage state;
- review age and stale-evidence counts;
- unreviewed, legacy, contradictory, inactive, rejected, and superseded records;
- automatic-operation coverage versus abstention rate;
- leftovers linked to exact immutable versions;
- lifecycle activity by reason and age.

Acceptance:

- every percentage has an explicit denominator and query timestamp;
- coverage never implies correctness or safety.

## P1.2 Frontend immutable evidence completion

Tasks:

- show exact policy ID, policy version, content hash, reviewer, and review time
  beside every leftover;
- load lifecycle events in the research evidence surface;
- show rejection/deactivation reason and actor;
- use active reviewed immutable policy versions in the leftover selector;
- retain inactive history for audit;
- add browser tests for exact provenance and withdrawn-version history;
- remove legacy policy/conversion consumers after import-tree proof.

## P1.3 Signed evidence documents

Tasks:

- optional detached signatures for import and lifecycle documents;
- signer identity and trust-root policy;
- signature verification before preflight;
- signed manifest retention;
- explicit unsigned-development mode;
- no claim that hashing alone authenticates a publisher.

# P1 — Complete preparation operations

## P1.4 Persist household resource calendars and schedules

Models:

- household resource and immutable calendar version;
- availability windows and recurrence rules;
- person-specific labor resources;
- approved schedule with source plan/profile/resource versions;
- status: draft, approved, invalidated, completed, cancelled;
- append-only schedule event ledger.

Rules:

- changing plan, servings, evidence version, or resource calendar invalidates
  dependent schedules;
- approval is explicit;
- no background execution or appliance control.

## P1.5 Plan-to-occurrence generation

Tasks:

- derive candidate meal occurrences from persisted plan meals;
- require explicit serving count and finish-time review;
- surface recipes without reviewed profiles;
- show profile version/hash before approval;
- never auto-submit generated occurrences;
- persist the confirmed occurrence set with the plan version.

## P1.6 Active labor, passive time, supervision, and transitions

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

## P1.7 Joint plan and schedule repair

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

## P1.8 Forecast baselines and uncertainty

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

## P1.9 Inventory costs and stochastic scenarios

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

## P1.10 Closed-loop forecast/policy benchmark

Require:

- common realized demand and lead-time paths;
- forecast metrics separate from operational metrics;
- policy hyperparameters declared and hashed;
- multi-seed confidence intervals;
- no automatic procurement model selection;
- human-reviewed candidate promotion only.

# P1 — Recommendation and preference platform

## P1.11 Real-data ranking protocol

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

## P1.12 Consent-based preference workflow

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

## P3.5 Clinical and health-outcome research

Any nutrition/health outcome, medication interaction, allergy-safety, or
condition-specific recommendation remains disabled until formal clinical
protocols, external validation, governance, monitoring, and regulatory review
are complete.

# Current execution order

1. Close one exact green direct-main workflow without weakening gates.
2. Complete frontend immutable policy/lifecycle provenance and browser tests.
3. Add generated frontend/OpenAPI schema drift validation.
4. Implement persisted household resource calendars and approved schedules.
5. Add plan-to-occurrence review and schedule invalidation.
6. Add authenticated Playwright/PostgreSQL and axe coverage.
7. Build evidence coverage/abstention dashboards.
8. Expand stochastic inventory and closed-loop policy evaluation.
9. Build consent-based real-data ranking workflows.
10. Continue P2/P3 research only through explicit data, validation, artifact,
    approval, rollback, and monitoring gates.
