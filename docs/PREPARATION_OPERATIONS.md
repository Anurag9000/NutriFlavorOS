# Persisted Preparation Operations

NutriFlavorOS persists preparation calendars, deterministic schedules, and explicit household execution events as a human-reviewed workflow. It does not control appliances, infer presence, verify cooking, measure temperature, or guarantee food safety or successful preparation.

## Migration and contract history

- `20260801_0009` — immutable resource calendars, resources, schedules, and lifecycle events.
- `20260801_0010` — complete scheduler request and request hash.
- `20260801_0011` — calendar, schedule, and event state constraints.
- `20260801_0012` — complete canonical occurrence document persistence.
- `20260802_0013` — optimistic household-plan lifecycle and append-only plan events.
- `20260802_0014` — append-only user-confirmed task execution events.

Current boundary:

- migration head `20260802_0014`;
- API `0.12.1`;
- OpenAPI contract `2026-08-02.6`;
- preparation bindings `2026-08-02.4`;
- household-plan bindings `2026-08-02.4`.

## Reviewed resource calendars

A calendar belongs to one household and declares:

- version, horizon, and timezone;
- resource IDs, labels, kinds, integer capacities, and explicit windows;
- review state, canonical UTC review time, reviewer, notes, and SHA-256;
- creator, request fingerprint, idempotency key, active state, and predecessor.

Only reviewed calendars can be active, and one active reviewed calendar is permitted per household. Activating a successor deactivates its predecessor and atomically invalidates every dependent draft or approved schedule.

### Structured calendar builder

The protected `/preparation/operations/calendars/new` route provides:

- person, burner, oven, counter, refrigerator, and custom templates;
- dynamic resource and multi-window editing;
- duplicate-ID, numeric, horizon, empty-window, and overlap validation;
- deterministic normalization;
- operational predecessor diff;
- canonical JSON import/export;
- timezone-aware review preview;
- mandatory human confirmations;
- automatic confirmation reset after any reviewed change or household/predecessor switch;
- owner-only activation.

Importing a draft never activates a calendar.

## Multi-window scheduling semantics

A resource may use a preserved legacy continuous interval or an explicit non-empty window list. The forms cannot be mixed. Windows are ordered, non-overlapping, and horizon-bounded.

Every task must fit entirely within one continuous containing window for every demanded resource. It cannot bridge a gap or cross an unavailable interval. Multi-resource tasks require simultaneous interval and cumulative-capacity feasibility.

The deterministic heuristic and bounded exact comparator share window, capacity, dependency, deadline, normalization, and utilization semantics.

## Approved source-plan prerequisite

Household plan generation is not approval.

A source-linked preparation schedule may be created only when:

- `source_plan_id` and `source_plan_version` are supplied together;
- the plan belongs to the route household;
- the exact optimistic version still matches;
- the plan status is `approved`.

A new plan is initially `draft`. Owner approval increments its version and records actor/time and an append-only plan event. The schedule retains the approved version, not the original draft version.

Rejection codes include `source_plan_not_approved` and `source_plan_version_mismatch`.

If plan cancellation races schedule creation, household serialization and the internal version recheck guarantee one of two outcomes:

1. cancellation commits first and schedule creation fails as stale; or
2. schedule creation commits first and cancellation immediately invalidates it.

## Canonical occurrence document

Schedule creation requires `PreparationOccurrenceSetDocument` with:

- document version;
- household ID;
- occurrence-set version;
- duration policy;
- occurrences containing occurrence ID, recipe ID, deadline, servings, and priority.

The server canonicalizes occurrence order and derives its SHA-256. A client cannot substitute a self-asserted hash.

Each compiled task must match occurrence and reviewed-profile provenance:

- occurrence and recipe IDs;
- servings, priority, and deadline;
- profile ID, version, and content hash;
- duration minimum/maximum and selected policy;
- task-template metadata.

Missing, extra, or contradictory profile/task provenance fails closed.

## Persisted schedule creation

A creation request carries:

1. active reviewed calendar ID;
2. optional exact approved source-plan ID/version;
3. complete occurrence document;
4. normalized profile-version map;
5. complete scheduler request;
6. complete deterministic response;
7. notes and idempotency key.

The API and authoritative persistence path:

1. authorize editor/owner access;
2. require approved source-plan state when linked;
3. lock household operation scope;
4. verify route/occurrence household equality;
5. verify active reviewed calendar identity, hash, and resources;
6. recheck source-plan household and version;
7. validate occurrence/profile/task/duration provenance;
8. replay deterministic scheduling;
9. require exact response equality and no unresolved tasks;
10. persist document, request, response, and all hashes;
11. append `created` in the same transaction.

The combined schedule hash binds calendar hash, optional plan pair, occurrence version/hash, profile versions, complete request, and response.

## Approval-time replay

Owner approval repeats the full integrity proof:

- require stored occurrence and request payloads;
- parse strict contracts;
- revalidate occurrence/profile/task/duration consistency;
- recompute occurrence/request hashes;
- verify active calendar and captured hash/resources;
- verify source-plan identity/version;
- replay scheduler and compare the response;
- recompute combined schedule hash;
- apply the optimistic transition only after all checks pass.

Tampering with occurrence, task, profile, request, response, plan, calendar, or hashes fails explicitly.

## Plan cancellation propagation

Cancelling a draft or approved household plan:

- increments the plan version and makes it terminal;
- releases its active inventory reservations;
- invalidates every linked preparation schedule still in `draft` or `approved`;
- records plan cancellation metadata including affected counts;
- appends one schedule invalidation event per affected schedule.

Completed, cancelled, and already invalidated schedules are not rewritten.

## Schedule lifecycle

Statuses:

- `draft`;
- `approved`;
- `invalidated`;
- `completed`;
- `cancelled`.

Transitions:

- draft to approved;
- draft to invalidated or cancelled;
- approved to completed, invalidated, or cancelled.

Terminal states are invalidated, completed, and cancelled. Every transition uses expected version, reason, metadata, and idempotency key. Identical retries return current state; contradictory reuse fails.

The normal HTTP `approved → completed` transition is guarded by the task execution ledger: every deterministic task must be explicitly `completed` or `skipped`. The established low-level transition service retains its historical completion behavior for compatibility with older internal callers; product code must use the guarded route or guarded completion service.

Roles:

- owner: calendar registration, schedule approval/invalidation, and plan approval;
- editor/owner: schedule persistence, task execution events, guarded completion/cancellation, and plan cancellation;
- viewer/editor/owner: calendars, schedules, task execution state, plan records, coverage, and events.

Cross-household or unauthorized access returns `404`.

## Append-only task execution ledger

Migration `20260802_0014` creates `preparation_task_execution_events`.

### Task identity and planned timing

Executable task IDs, planned starts, and planned finishes come only from the persisted deterministic schedule response. The server rejects unknown task IDs, duplicate persisted task IDs, incomplete schedules, or schedules with no deterministic tasks.

### States and transitions

Task states:

- `planned`;
- `in_progress`;
- `completed`;
- `skipped`.

Allowed events:

- `started`: planned to in progress;
- `completed`: in progress to completed;
- `skipped`: planned or in progress to skipped.

Completed and skipped are terminal. Completion requires a prior explicit start event. The completion minute cannot precede the confirmed start minute.

### Dependency chronology

A task cannot start until every deterministic dependency is explicitly completed or skipped. The server derives dependency IDs from the persisted schedule and returns `task_dependencies_not_terminal` with blocking IDs when chronology is violated.

A skipped prerequisite is treated as terminal evidence, not as proof that dependent work remains semantically valid. The household remains responsible for deciding whether proceeding is appropriate; future minimal-change repair must model this explicitly.

### Actual minutes and deviation evidence

Every event carries a horizon-relative `actual_minute`.

- Start deviation = actual start minute − planned start minute.
- Completion deviation = actual completion minute − planned finish minute.
- Skip deviation is zero because a skip is a categorical terminal decision rather than a timing observation.

A nonblank reason is mandatory for every skip and every nonzero start or completion deviation. Optional notes and metadata retain human-entered operational context.

### Optimistic versions and idempotency

Every task event:

- requires the current schedule optimistic version;
- increments that version by exactly one;
- stores versions before and after;
- uses a schedule-scoped idempotency key and canonical request fingerprint;
- returns the existing event for an exact retry;
- rejects contradictory key reuse;
- serializes through the same household operation lock used by schedule mutations.

A task event does not change schedule status. Status remains `approved` until guarded completion, cancellation, or invalidation.

### API

Viewer-authorized read:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/task-execution`

Editor/owner mutations:

- `POST .../tasks/{task_id}/start`;
- `POST .../tasks/{task_id}/complete`;
- `POST .../tasks/{task_id}/skip`.

Each mutation returns the updated schedule version, current task state, and append-only event.

### Frontend

The protected `/preparation/operations/execution` workspace provides household/schedule selection, progress, accessible task cards, actual-minute/reason/notes inputs, start/completion/skip confirmations, viewer read-only behavior, guarded final completion, and append-only actor/transition/deviation/version history.

Nothing is recorded on page load. No local timer, reminder, or UI state implies task execution.

## Append-only schedule and plan evidence

Schedule events retain actor, from/to state, reason, metadata, idempotency, fingerprint, and time. Database constraints permit only valid event/state pairs.

Household plan events retain equivalent transition provenance for approval and cancellation. Schedule invalidations caused by plan cancellation include source-plan ID/version and cancellation reason.

Task execution events remain separate from schedule lifecycle events so task evidence cannot be mistaken for a schedule status transition.

## Legacy schedules

Replay state is explicit:

- `replayable`;
- `legacy_request_missing`;
- `legacy_occurrence_set_missing`.

Legacy rows remain readable but cannot be approved. An exact creation retry may backfill missing replay/occurrence payloads only when stored identity and hashes match.

Task execution additionally requires a complete deterministic response with at least one scheduled task and no unresolved tasks.

## Provenance and execution coverage

`GET /api/v1/households/{household_id}/preparation-operations/coverage` returns two deliberately separate metric families.

### Operational provenance

- total, reviewed, and active reviewed calendars;
- schedule totals and complete lifecycle state map;
- replay-state counts;
- occurrence-document, scheduler-request, and replayable-schedule numerators and ratios;
- replayable drafts;
- exact source-plan linkage;
- append-only schedule event total;
- latest calendar and schedule timestamps.

### Task execution evidence

Execution scope includes schedules currently `approved` or `completed`, plus historical schedules that retain task events after later cancellation or invalidation.

The endpoint reports:

- execution-scope schedule count;
- currently approved execution schedule count;
- schedules with at least one task event;
- structurally invalid schedule/event-history count;
- deterministic task count;
- planned, in-progress, completed, and skipped state counts;
- terminal task count;
- fully terminal schedule count;
- task-event total;
- nonzero-deviation event count;
- skipped-event count and skipped events with nonblank reasons;
- execution-scope schedule-history ratio;
- deterministic task-terminality ratio;
- latest task-event timestamp.

The service parses deterministic schedule responses and replays task events structurally in order. Schedules with unresolved work, no tasks, duplicate task IDs, unknown dependencies, unknown event tasks, inconsistent from-state history, or invalid event targets are excluded from task-state denominators and counted as invalid. This prevents malformed history from inflating apparent completion.

Warnings expose missing active calendars, legacy provenance gaps, missing source-plan linkage, absent task history, invalid execution histories, orphaned events, or skipped events lacking reasons.

### Interpretation boundary

Coverage reports record presence, structural consistency, and user-entered claims. It does not prove:

- that cooking occurred;
- that timing entries are accurate;
- task performance or quality;
- nutritional correctness;
- appliance condition;
- temperature or contamination state;
- food safety.

The frontend presents provenance and execution sections independently and never combines them into one misleading score.

## Concurrency evidence

Configured PostgreSQL probes cover:

- identical calendar retries;
- identical schedule retries;
- competing schedule approval/cancellation;
- calendar supersession versus approval;
- identical plan approval retries;
- competing plan approval/cancellation;
- identical task-start retries collapsing to one event;
- competing start/skip decisions producing one winner.

Task and schedule mutations share household serialization and exact optimistic-version checks.

## Frontend routes

- `/household/plans` — exact plan review, approval, cancellation, and events;
- `/household/plans/occurrences` — explicit approved-plan occurrence confirmation;
- `/preparation/operations` — calendars, schedules, hashes, replay state, transitions, and schedule events;
- `/preparation/operations/execution` — explicit task execution and guarded completion;
- `/preparation/operations/calendars/new` — structured reviewed calendar builder;
- `/preparation/operations/coverage` — separate provenance and execution denominators.

`preparation-operations-handoff-v2` transfers occurrence, profile, optional plan, resource, request, and deterministic response data without automatic persistence or approval.

## Deliberate limitations

- Plan approval is household confirmation, not clinical or nutritional certification.
- Availability is declared, not inferred.
- Execution events are user-entered claims; the system does not observe execution.
- Temperature, contamination, equipment condition, and safe food state are not verified.
- Plan/calendar changes invalidate dependent work but do not create or approve replacements.
- Structured final persistence review, timers/reminders, minimal-change repair, and joint optimization remain incomplete.
- Presence sensors, appliance integrations, autonomous procurement, and control remain disabled pending separate validation and governance.
- Hosted workflow runs must be inspected before the current `main` commit is described as green.
