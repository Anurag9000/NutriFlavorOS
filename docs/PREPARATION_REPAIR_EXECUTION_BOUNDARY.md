# Preparation Repair and Task-Execution Boundary

## Core rules

Two independent rules protect execution history.

1. A preparation schedule with any append-only task-execution event is not a valid source for the current ordinary minimal-change repair proposal lifecycle.
2. Once a source schedule version has an accepted repair replacement, that source remains readable historical evidence but cannot receive any new task-execution event or schedule-completion action.

Schedule lifecycle status alone is therefore insufficient to determine repairability or executability.

## Repair creation after execution history

Before repair computation begins, proposal creation queries `preparation_task_execution_events` for the exact source schedule.

When any event exists, creation fails closed with HTTP `409` and code:

`repair_source_has_execution_history`

The source schedule, proposal table, and task history remain unchanged.

## Proposal staleness after execution begins

A proposal can be created while its source has no execution history and become stale later when a user starts, completes, or skips a task. Proposal reads recompute staleness and include:

`source_schedule_has_execution_history`

The immutable proposal remains readable, but `current` becomes `false`. A source-version stale reason can appear simultaneously because every task event increments the schedule version.

Proposal acceptance revalidates the same boundary under household and source locks. Execution beginning before or during acceptance prevents ordinary accepted-draft persistence.

## Accepted replacement execution boundary

Migration `20260802_0018` and the source-level acceptance guard allow only one accepted replacement per source schedule/version.

After acceptance:

- the source schedule is never updated or deleted;
- its existing task-event history remains readable;
- no new task may start, complete, or skip on the source;
- the source schedule cannot be completed;
- the new replacement begins as `draft`;
- the replacement must undergo separate owner approval and method-aware replay;
- only the separately approved replacement may become execution eligible.

A forbidden source mutation fails with HTTP `409` and code:

`source_schedule_has_accepted_replacement`

The structured conflict includes:

- accepted proposal ID;
- immutable acceptance ID;
- replacement schedule ID;
- replacement status and version where applicable.

The task-execution mutation route uses a household-locked replacement guard. Client behavior cannot weaken this server authority.

## Task-execution eligibility

The viewer-authorized preflight endpoint is:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/task-execution-eligibility`

It reports exactly one reason partition:

- `eligible` — the schedule is approved and has no accepted replacement block;
- `schedule_not_approved` — lifecycle state is not executable;
- `source_schedule_has_accepted_replacement` — the schedule is historical source evidence and exposes the exact replacement chain.

The protected task-execution workspace reads this evidence before enabling controls. While eligibility is loading, controls remain disabled. A blocked source displays proposal, acceptance, replacement schedule, replacement status/version, and source event count. It can link or switch to the replacement, but it cannot submit a source mutation.

The mutation function independently reasserts eligibility immediately before submission. This frontend check improves clarity; the backend guard remains authoritative against stale tabs, direct API clients, retries, and races.

## Why automatic immutable-task conversion is prohibited

Current repair contracts can pin task IDs to prior planned placements, but execution evidence contains more than placement:

- confirmed actual start or finish minute;
- task state and terminality;
- deviation evidence and mandatory reasons;
- dependency chronology;
- optimistic schedule versions;
- append-only event identity and idempotency;
- actor and UTC event provenance.

Silently translating completed or in-progress work into ordinary immutable tasks would discard or reinterpret evidence. The current engine abstains instead of claiming execution-aware repair.

## Requirements for execution-aware repair

A future engine must:

1. treat every existing task event as immutable evidence;
2. preserve completed and skipped terminal states;
3. preserve confirmed starts and prohibit moving executed work;
4. preserve dependency chronology established by events;
5. prevent removal or operational-signature changes for executed tasks;
6. distinguish planned remaining work from historical actual work;
7. retain source schedule/event hashes, actors, timestamps, fingerprints, and optimistic versions;
8. define behavior for infeasible remaining work without rewriting history;
9. require explicit human review and changed-task acknowledgement;
10. create a new draft rather than mutate the executed source;
11. keep owner approval, future task execution, and completion separate;
12. add PostgreSQL races for execution onset during computation, proposal creation, acceptance, approval, and replacement selection.

## Completion authority

The normal product completion endpoint requires every deterministic task to be explicitly completed or skipped. Static repository analysis rejects new product code that directly requests low-level schedule completion outside the task-terminality guard.

A historical generic transition service retains compatibility behavior and remains scheduled for migration into the lowest authoritative terminality layer. It must not be used as a product bypass.

## Verification

Configured verification includes:

- source-first: start a task, then reject proposal creation with `repair_source_has_execution_history`;
- proposal-first: create a proposal, begin execution, and mark it stale;
- acceptance race: either source execution wins or accepted-draft creation wins, never both;
- replacement guard: accepted source mutations fail with `source_schedule_has_accepted_replacement`;
- replacement success: separately approved replacement task execution remains available;
- eligibility service/API tests for approved, draft, replaced-source, and approved-replacement states;
- frontend tests proving controls are disabled and exact replacement identities are displayed;
- static authority scans for proposal, execution, eligibility, and completion paths;
- fresh SQLite and PostgreSQL workflow configuration with retained machine-readable evidence.

Configured tests and workflows are not represented as executed green evidence until the exact current hosted run and artifacts are observed.

## Non-claims

This boundary does not infer whether a task actually occurred. It preserves explicit stored user-entered events only. It does not observe people, appliances, temperatures, contamination, cooking quality, or food safety.
