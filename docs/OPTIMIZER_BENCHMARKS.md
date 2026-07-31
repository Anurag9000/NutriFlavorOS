# Optimizer benchmark protocol

NutriFlavorOS exposes several planner implementations behind a shared option/target contract:

- deterministic personal weekly beam search;
- deterministic household pantry-aware beam search;
- exhaustive pure-Python Pareto enumeration for bounded fixture problems;
- optional OR-Tools CP-SAT;
- optional PuLP/CBC MILP.

The exact solvers are optional research dependencies and are never silently substituted. Hard allergen and dietary filtering must happen before any benchmark input is built. A benchmark score is not evidence of nutritional, medical, or clinical validity.

## Deterministic synthetic scenario

Generate a synthetic problem that contains no user records and run every available baseline three times:

```bash
python scripts/benchmark_planners.py \
  --generate-seed 17 \
  --slots 7 \
  --options-per-slot 5 \
  --repeats 3 \
  --save-problem reports/generated/problem_seed_17.json \
  --output reports/generated/planner_benchmark_seed_17.json
```

The generator is deterministic for the tuple `(seed, slots, options_per_slot)`. The report includes a SHA-256 fingerprint of the complete problem so results from different inputs cannot be compared accidentally.

## Benchmark an explicit problem

```bash
python scripts/benchmark_planners.py benchmarks/planner_small.json \
  --repeats 5 \
  --max-objective-gap 0.05 \
  --output reports/generated/planner_small_report.json
```

A problem file must contain:

```json
{
  "schema_version": 1,
  "targets": {
    "calories": 1800,
    "protein": 100,
    "carbs": 220,
    "fat": 55,
    "cost_limit": 30
  },
  "options": [
    {
      "slot": "breakfast",
      "option_id": "breakfast-oats",
      "calories": 420,
      "protein": 20,
      "carbs": 68,
      "fat": 8,
      "cost": 3.5,
      "taste": 0.8,
      "variety": 0.7,
      "pantry": 0.9
    }
  ]
}
```

Every slot must have at least one option and every `option_id` must be unique.

## Optional solver requirements

Install research dependencies when exact-solver execution is required:

```bash
pip install -r backend/requirements-research.txt
python scripts/benchmark_planners.py benchmarks/planner_small.json \
  --require-solver cp_sat \
  --require-solver milp
```

Without `--require-solver`, an unavailable optional dependency is recorded as `dependency_unavailable` and does not fail the whole report. A required unavailable solver fails the regression gate.

## Report and gate semantics

Report schema version 2 records:

- problem fingerprint, generator metadata, slot count, option count, and targets;
- Python/platform metadata;
- every repeat's selected IDs, native objective, common audited objective, diagnostics, and elapsed time;
- missing slots, duplicate slots, unknown IDs, duplicate IDs, and cost-limit violations;
- deterministic replay status;
- minimum, median, and maximum runtime;
- common-objective gap to the best valid available solver;
- machine-readable gate failures.

The CLI returns exit code `2` when a regression gate fails. `--allow-gate-failures` should be used only for exploratory reports, never for release validation.

The default `main` workflow runs a bounded seeded Pareto benchmark after the backend test suite. CP-SAT and MILP remain optional and should be exercised in research environments where their pinned dependencies are installed.

## Promotion requirements

A planner may be considered for runtime promotion only after:

1. deterministic replay across representative seeds;
2. constraint-equivalence tests against the production hard-filter surface;
3. explicit infeasibility diagnostics;
4. scale and latency measurements with declared hardware/software versions;
5. dataset provenance and leakage review;
6. common-objective parity against a trusted exact or exhaustive reference on small problems;
7. human review of safety-sensitive failure modes.
