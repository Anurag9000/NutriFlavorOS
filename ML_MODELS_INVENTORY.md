# NutriFlavorOS Model and Algorithm Inventory

**Reviewed:** 2026-08-06  
**Status:** research and experimental implementations; no blanket production, convergence, accuracy, or deployment claim.

## Interpretation rules

A Python class, architecture, checkpoint path, training script, or catalog entry is not evidence that a model has been trained, converged, evaluated, approved, or deployed. A model may be described as validated only when the repository contains an immutable dataset/version manifest, split definition, environment lock, training run, artifact hash, evaluation report, calibration and robustness evidence, model card, approval decision, and deployment record.

NutriFlavorOS must not use learned outputs to diagnose, treat, or predict medical conditions, allergies, glucose response, microbiome state, mental health, stress, sleep outcomes, or food safety.

## Current system-of-record algorithms

The most mature repository paths are deterministic, evidence-driven algorithms rather than learned models:

- Constraint-aware meal-plan generation with explicit inputs, bounded search, and diagnostics.
- Pantry/leftover FEFO selection and transactional material accounting.
- Approved-plan occurrence confirmation against exact reviewed preparation profiles.
- Deterministic dependency/resource preparation scheduling.
- Task execution eligibility and terminality checks.
- Greedy and bounded exact repair-proposal generation.
- Lifecycle, replay, idempotency, concurrency, and recovery validators.

These algorithms still require environment-specific verification and must not be described as globally optimal unless an exact solver records an optimality proof or bound.

## Experimental learned-model code

The repository has historically included experimental implementations or placeholders in areas such as:

- Taste or recipe preference scoring.
- Health-related sequence prediction prototypes.
- Reinforcement-learning meal-planning experiments.
- Grocery or household-demand prediction.
- Recipe text generation.
- Food-image classification or estimation.
- Online-learning orchestration.

Their presence must be interpreted as research code only. The former claims of “trained to convergence,” “95%+ accuracy,” production weights, 10,000+ successful episodes, or validated health-outcome prediction are not established by this inventory.

## Required evidence per learned model

Every model promoted beyond an isolated experiment must include:

1. **Purpose and boundary** — supported decision, prohibited uses, fallback, and human authority.
2. **Data manifest** — source, license, consent, lineage, time range, schema, hashes, retention, and deletion semantics.
3. **Split manifest** — household-disjoint and time-forward partitions with leakage checks.
4. **Feature contract** — point-in-time availability, provenance, missingness, units, transformations, and version.
5. **Baseline comparison** — deterministic heuristic and simple statistical baselines.
6. **Training record** — code SHA, environment lock, seed, hyperparameters, hardware, duration, and immutable logs.
7. **Artifact record** — weights hash, serialization format, dependency versions, and integrity checks.
8. **Evaluation** — task metrics, calibration, abstention coverage, subgroup/worst-case behavior, robustness, latency, and cost.
9. **Model card** — intended use, limitations, failure modes, safety boundary, and monitoring plan.
10. **Approval and rollback** — named approver, shadow period, activation record, kill switch, and rollback evidence.

## Recommended implementation order

### Tier 0 — deterministic baselines

- Seasonal-naive and moving-average demand forecasts.
- Croston and TSB intermittent-demand baselines.
- Rule-based preference and substitution ranking.
- Deterministic waste/expiry risk scoring.
- Current bounded scheduler plus CP-SAT/MILP benchmarks.

### Tier 1 — low-risk supervised experiments

- Gradient-boosted demand and duration models.
- Pairwise/listwise preference ranking with calibrated confidence.
- Anomaly detection for data-quality review, never automatic user judgment.
- Conformal prediction intervals and abstention.

### Tier 2 — retrieval and structured intelligence

- Typed ingredient-substitution graph and evidence-aware retrieval.
- OCR/barcode candidates with confidence and mandatory review below threshold.
- Vision-assisted ingredient suggestions with no automatic safety or quantity authority.

### Tier 3 — advanced research only after evidence maturity

- Robust/stochastic optimization under uncertainty.
- Contextual bandits with conservative constraints and offline evaluation.
- Graph neural networks only when edge semantics, labels, and leakage controls justify them.
- Generative recipe assistance only with hard post-generation validation, provenance, and human approval.

## Prohibited inventory labels without evidence

Do not label any model as:

- production ready;
- trained to convergence;
- deployed;
- clinically validated;
- medically accurate;
- food-safety certified;
- guaranteed optimal;
- guaranteed to improve health, retention, savings, waste, or engagement.

## Current conclusion

NutriFlavorOS has a broad research surface and mature deterministic workflow infrastructure, but this document does not certify any learned model as trained or deployable. Future model work should be promoted through the evidence gates above, one narrowly scoped decision at a time.
