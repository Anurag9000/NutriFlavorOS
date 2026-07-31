# Research Platform

The research package separates ideas from validated product behavior. A catalog entry means “this is a defined experiment contract,” not “this model is trained, accurate, safe, or enabled.”

## Catalog scope

The catalog currently contains:

- 28 task contracts across retrieval, recommendation, vision, NLP, optimization, forecasting, sustainability, safety, data quality, reliability, preference learning, bandits, continual personalization, causal analysis, and privacy;
- 24 dataset families;
- 57 model and algorithm families;
- 21 experiment contracts;
- 26 product/research feature contracts.

Important external families include USDA FoodData Central, Recipe1M+, Nutrition5k, Food-101, FoodSeg103, DishSeg24k, UECFOOD256, VireoFood172, Grocery Store Dataset, Open Food Facts, NHANES, EPIC-KITCHENS, Ego4D, AGRIBALYSE, ecoinvent, Water Footprint data, Food2K, and ISIA Food-500. Access, license, consent, and geography constraints must be reviewed before use.

## Implemented executable baselines

- TF-IDF recipe retrieval;
- popularity and explicit-content preference ranking;
- moving-average and Croston intermittent-demand forecasting;
- ridge regression;
- rule-based ingredient parsing and culinary substitution;
- deterministic horizon-level beam-search meal optimization.

## Metrics

Implemented metrics cover MAE, RMSE, WAPE, R², pinball loss, precision/recall/MRR/NDCG, Brier score, expected calibration error, interval coverage, mean IoU, IPS, SNIPS, and deterministic bootstrap intervals.

## Reproducibility and leakage controls

- Experiment configs use explicit IDs, baselines, seeds, parameters, notes, and user-data consent flags.
- Potential user-owned paths are rejected unless explicitly permitted.
- Manifests record environment, seed, configuration, dataset/model fingerprints, metrics, warnings, and artifact checksums.
- Group-aware splitting keeps repeated entities in one partition.
- Temporal splitting prevents future examples entering earlier partitions.
- The offline CLI uses a fixed implementation whitelist and never imports arbitrary classes from input.

## Dataset and model cards

Cards record provenance, source URLs, license, intended/prohibited use, personal-data and consent status, leakage controls, quality checks, limitations, artifact checksums, metrics, calibration, subgroups, OOD evaluation, and promotion gates.

High-risk artifacts require offline benchmark, OOD, calibration, subgroup, and human-review gates. Clinical-risk artifacts additionally require external validation, uncertainty coverage, contraindication safety, clinical review, documented clinical validation, and a human approval identifier.

## Artifact registry

The offline local registry:

- writes atomically;
- validates catalog IDs;
- hashes artifacts with SHA-256;
- detects tampering;
- supports registered, candidate, champion, rejected, and archived stages;
- requires candidate stage before champion;
- archives an older champion when a new version is promoted;
- never auto-loads or auto-promotes a request-time model.

## Drift

Implemented diagnostics include population stability index, two-sample KS statistic, standardized mean shift, and categorical total variation. They report drift; they do not retrain or promote automatically. Thresholds must be calibrated per artifact.

## FoodData Central adapter

The adapter is disabled by default, requires an API key, preserves USDA identifiers and missing values, records source/retrieval/license metadata, and never falls back to mock nutrition values.

## Disabled research paths

Multimodal nutrition estimation, food segmentation, recipe generation, medical/allergen safety models, contextual bandits, continual personalization, N-of-1 health analyses, and request-time online learning remain research-only or blocked. They must pass their cards, data, split, evaluation, integrity, promotion, shadow, and rollback gates before any product enablement.
