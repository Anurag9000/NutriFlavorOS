# Deterministic Preparation-Schedule Repair

## Purpose

NutriFlavorOS can compute a new preparation-schedule candidate after an explicit scheduling problem changes. The repair subsystem minimizes disruption relative to a previously complete deterministic schedule while rechecking the revised horizon, resource calendars, capacities, task windows, deadlines, and dependency graph.

Repair is advisory computation only. It does not mutate the previous request or response, write a database row, approve a schedule, create a task-execution event, infer that work occurred, or decide that food is safe. Every result carries three enforced boundary fields:

- `requires_human_acceptance = true`;
- `accepted = false`;
- `persistence_performed = false`.

The result model rejects contradictory values. A separate reviewed product action must be designed before a repair can become a persisted draft, and approval and execution must remain separate lifecycle transitions.

## Inputs

`PreparationScheduleRepairRequest` contains:

- the exact previous `PreparationScheduleRequest`;
- its complete deterministic `PreparationScheduleResponse`;
- the revised `PreparationScheduleRequest`;
- optional immutable task IDs;
- either `greedy_min_change` or `bounded_exact_min_change`;
- an explicit `allow_partial` choice;
- non-negative objective weights;
- bounded exact-search limits.

The previous response must be complete, non-empty, and aligned with the previous request horizon and granularity. The engine also validates that the previous request and response have the same task set and operational snapshots.

## Feasibility model

Every repaired placement is checked against the same declared scheduling semantics used by the deterministic preparation scheduler:

- finite scheduling horizon and granularity;
- task duration, earliest start, and latest finish;
- acyclic dependency graph and dependency chronology;
- declared resource demands;
- declared resource capacities;
- one or more non-overlapping availability windows;
- full containment of a task inside one continuous resource window;
- cumulative capacity across overlapping work.

Unknown dependencies, duplicate task or resource IDs, overlapping resource windows, malformed previous snapshots, and infeasible immutable work fail closed with stable `PreparationRepairError` codes and structured details.

## Immutable task semantics

An immutable task is pinned to its exact prior start and finish. It must:

- still exist in the revised task set;
- retain its operational signature;
- remain feasible in the revised problem;
- have every required predecessor pinned as part of the immutable closure.

The engine does not silently move, remove, resize, or reinterpret immutable work. A violation returns a structured conflict such as `immutable_task_removed`, `immutable_task_changed`, `immutable_dependency_not_pinned`, or `immutable_task_infeasible`.

## Objective and deterministic tie breaking

Repair uses a lexicographic objective before applying the configured weighted value:

1. minimize unscheduled revised tasks;
2. minimize changed tasks;
3. minimize total absolute displacement from prior starts;
4. minimize makespan;
5. use stable task-ID/start ordering as the final deterministic tie break.

The result reports preserved, moved, added, removed, and unscheduled tasks separately. It also reports objective components, utilization, peak demand, search diagnostics, warnings, and canonical SHA-256 hashes for the previous schedule, revised request, and repaired response.

## Strategies

### Greedy minimal change

The default strategy traverses the validated dependency order, attempts each prior start first, then examines feasible starts by absolute displacement and stable minute order. It is deterministic and suitable as the general baseline, but it is not represented as globally optimal.

### Bounded exact minimal change

The exact strategy enumerates a bounded candidate space for small instances under the same feasibility semantics. It is used as a comparator and benchmark oracle. When configured limits are exceeded, the result records truncation and falls back deterministically rather than claiming an exact optimum.

## Partial repair

Partial output is prohibited unless `allow_partial` is explicitly true. In partial mode every unresolved task retains a structured reason, such as missing resource, blocked dependency, deadline infeasibility, availability-window infeasibility, or capacity infeasibility. A partial result is not an executable complete schedule.

## Interfaces

### Authenticated HTTP

`POST /api/v1/preparation/schedule/repair`

The endpoint requires authentication, performs no database dependency or persistence call, returns `PreparationScheduleRepairResult`, and maps `PreparationRepairError` to HTTP `409` with the stable structured error payload. Pydantic contract violations remain HTTP `422`.

### Offline CLI

`scripts/repair_preparation_schedule.py` consumes a strict JSON repair request and emits a deterministic JSON result. CLI output explicitly labels persistence as not performed and human acceptance as required. It is intended for reproducible offline analysis, not autonomous schedule replacement.

### Benchmark

`scripts/benchmark_preparation_repair.py` runs committed repair cases and emits a retained machine-readable report. Cases cover identity repair, capacity reduction, immutable anchors, dependency chronology, partial infeasibility, task additions/removals, input-order invariance, exact-versus-greedy comparison, and bounded fallback.

## Verification

The repair-specific workflow compiles the API, contracts, engine, CLI, benchmark, and validator; validates the advisory/API contract; executes unit, metamorphic, API, CLI, and benchmark tests; then uploads the benchmark report.

Contract validation also rejects persistence-like calls in the engine or authoritative API function and verifies that the repair route is authenticated in generated OpenAPI.

## Non-claims

The subsystem does not claim:

- global optimality for greedy or truncated exact runs;
- representative product-scale performance;
- observed human presence or task completion;
- appliance state or autonomous control;
- time-temperature evidence;
- contamination assessment;
- nutrition or clinical validation;
- food-safety approval.

## Remaining product work

- protected structured repair review comparing old and proposed schedules;
- explicit reviewer confirmation for every moved, added, removed, or unresolved task;
- a separate idempotent action that persists an accepted result as a new draft while preserving both source hashes;
- owner approval and invalidation rules for accepted repaired drafts;
- joint meal-plan and preparation repair;
- large-neighborhood and relaxation-based repair for larger instances;
- infeasibility-core explanations;
- representative-scale latency and optimality-gap evidence;
- authenticated PostgreSQL-backed browser journeys, axe checks, keyboard-only operation, screen-reader assertions, and visual regression.
