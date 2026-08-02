# Preparation Repair and Task-Execution Boundary

## Core rules

Three independent rules protect execution history.

1. A preparation schedule with any append-only task-execution event is not a valid source for the current ordinary minimal-change repair proposal lifecycle.
2. Once a source schedule version has an accepted repair replacement, that source remains readable historical evidence but cannot receive any new task-execution event or schedule-completion action.
3. Every new schedule `completed` transition, including a direct low-level service call, must prove that all deterministic tasks are explicitly completed or skipped.

Schedule lifecycle status alone is therefore insufficient to determine repairability, executability, or completion eligibility.

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

The structured conflict includes accepted proposal ID, immutable acceptance ID, replacement schedule ID, and replacement status/version where applicable.

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

## Lowest-layer schedule completion authority

The exported `backend.services.preparation_operations_service.transition_schedule` is the lowest authoritative lifecycle transition. A `COMPLETED` request cannot bypass task terminality by calling that service directly.

The public service is an authority facade over a preserved implementation module. It retains established calendar/schedule behavior while adding completion proof before delegation:

1. acquire the household transaction/advisory lock;
2. preserve exact event-idempotency retry and contradictory-key handling;
3. preserve missing-resource, optimistic-version, and invalid-lifecycle error precedence;
4. for a valid new `approved -> completed` request, lock the schedule;
5. reconstruct deterministic tasks and append-only execution history;
6. reject with `schedule_tasks_not_terminal` and sorted remaining task IDs unless every task is `completed` or `skipped`;
7. delegate lifecycle mutation, event append, commit, and exact retry semantics to the preserved implementation.

`complete_schedule_with_execution_guard` remains as a compatibility-named entry point, but it contains no independent lock, query, terminality proof, or commit path. It delegates directly to the authoritative transition.

Only the public facade may import the preserved implementation module. Static repository validation rejects any product module that imports the compatibility implementation directly.

## Final-task concurrency boundary

Task execution events and schedule lifecycle completion use the same household transaction/advisory lock and schedule optimistic version.

A real PostgreSQL probe races:

- the final in-progress task’s `completed` event; and
- schedule completion using the same pre-event schedule version.

The schedule completion cannot win ahead of the task event. It must fail with either:

- `schedule_tasks_not_terminal` when it obtains the lock first; or
- `schedule_version_conflict` when the final task event commits first.

After the final task event commits, a fresh completion request using the new schedule version succeeds and appends exactly one schedule `completed` event.

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

## Verification

Configured verification includes:

- source-first: start a task, then reject proposal creation with `repair_source_has_execution_history`;
- proposal-first: create a proposal, begin execution, and mark it stale;
- acceptance race: either source execution wins or accepted-draft creation wins, never both;
- replacement guard: accepted source mutations fail with `source_schedule_has_accepted_replacement`;
- replacement success: separately approved replacement task execution remains available;
- direct low-level completion rejection before task terminality;
- explicit task events followed by successful direct completion and exact retry;
- real PostgreSQL final-task-versus-schedule-completion serialization;
- eligibility service/API tests for approved, draft, replaced-source, and approved-replacement states;
- frontend tests proving controls are disabled and exact replacement identities are displayed;
- static authority scans that require the facade, forbid implementation bypass, and prohibit duplicate wrapper authority;
- fresh SQLite and PostgreSQL workflow configuration with retained machine-readable evidence.

Configured tests and workflows are not represented as executed green evidence until the exact current hosted run and artifacts are observed.

## Non-claims

This boundary does not infer whether a task actually occurred. It preserves explicit stored user-entered events only. It does not observe people, appliances, temperatures, contamination, cooking quality, or food safety.
