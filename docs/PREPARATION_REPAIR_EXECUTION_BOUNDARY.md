# Preparation Repair and Task-Execution Boundary

## Rule

A preparation schedule with any append-only task-execution event is not a valid source for the current minimal-change repair proposal lifecycle.

This includes schedules that remain in the `approved` lifecycle state but already contain a user-confirmed `started`, `completed`, or `skipped` task event. Schedule lifecycle status alone is therefore insufficient to determine repairability.

## Creation behavior

Before repair computation begins, proposal creation queries `preparation_task_execution_events` for the exact source schedule.

When any event exists, creation fails closed with HTTP `409` and code:

`repair_source_has_execution_history`

The source schedule, proposal table, and task history remain unchanged.

## Read-time staleness

A proposal can be created while its source has no execution history and become stale later when a user starts, completes, or skips a task. Proposal reads therefore recompute staleness and include:

`source_schedule_has_execution_history`

The proposal remains immutable and readable as historical evidence, but `current` becomes `false`. Other stale reasons such as source version changes may appear simultaneously because every task event increments the schedule version.

## Why automatic immutable-task conversion is prohibited

Current repair contracts can pin explicit task IDs to their prior planned placement, but execution evidence contains more than placement:

- confirmed actual start or finish minute;
- task state and terminality;
- deviation evidence and mandatory reasons;
- dependency chronology;
- optimistic schedule versions;
- append-only event identity and idempotency;
- actor and UTC event provenance.

Silently translating completed or in-progress work into ordinary immutable tasks would discard or reinterpret this evidence. The current engine therefore abstains instead of claiming execution-aware repair.

## Requirements for execution-aware repair

A future engine must:

1. treat every existing task event as immutable evidence;
2. preserve completed and skipped terminal states;
3. preserve a confirmed start and prohibit moving it later or earlier;
4. preserve dependency chronology already established by events;
5. prevent removal or operational-signature changes for executed tasks;
6. distinguish planned remaining work from historical actual work;
7. retain source schedule/event hashes and optimistic versions;
8. define behavior for newly infeasible remaining work without rewriting history;
9. require explicit human review and acceptance;
10. create a new draft rather than mutate the executed source schedule;
11. keep approval, execution, and schedule completion as separate actions;
12. add PostgreSQL races for execution beginning during proposal creation or acceptance.

## Verification

Configured verification includes:

- a source-first test: start a task, then attempt proposal creation and require `repair_source_has_execution_history`;
- a proposal-first test: create a proposal, then start a task and require `source_schedule_has_execution_history` with `current=false`;
- a static contract ensuring the execution-history check occurs before repair computation;
- a static contract ensuring the API uses execution-aware proposal reads;
- a fresh-database focused workflow.

Configured tests and workflows are not represented as executed green evidence until the exact hosted run is observed.

## Non-claims

This boundary does not infer whether a task actually occurred. It preserves only explicit stored user-confirmed events. It does not observe people, appliances, temperatures, contamination, cooking quality, or food safety.
