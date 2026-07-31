# Optimizer baselines

NutriFlavorOS exposes four offline planner baselines with a shared option/target contract:

- deterministic household pantry-aware beam search;
- exhaustive Pareto enumeration for small fixture problems;
- optional OR-Tools CP-SAT;
- optional PuLP MILP.

The exact solvers are optional research dependencies and are never silently substituted. `scripts/benchmark_planners.py` reports unavailable dependencies, objective components, feasibility, selections, and elapsed time. Hard dietary/allergen filtering must happen before every solver. Benchmark success is not evidence of nutritional or clinical validity.

Use:

```bash
pip install -r backend/requirements-research.txt
python scripts/benchmark_planners.py --output reports/generated/planner_benchmarks.json
```

A planner may be considered for runtime promotion only after deterministic replay, constraint-equivalence tests, representative scale/latency benchmarks, infeasibility diagnostics, and reviewed data coverage.
