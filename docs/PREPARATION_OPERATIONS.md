# Persisted Preparation Operations

NutriFlavorOS persists reviewed resource calendars, deterministic preparation schedules, repair evidence, accepted replacement drafts, derivation provenance, and explicit household task events as a human-reviewed workflow. It does not control appliances, infer presence, verify cooking, measure temperature, or guarantee food safety or successful preparation.

## Current boundary

- Alembic head: `20260802_0018`
- API: `0.15.2`
- OpenAPI contract: `2026-08-02.12`
- Preparation frontend binding: `2026-08-02.4`
- Household-plan frontend binding: `2026-08-02.4`

Configured workflows and tests are not reported as green until the exact current hosted run and artifacts are observed.

## Migration history

- `20260801_0009` — immutable resource calendars, resources, schedules, and lifecycle events.
- `20260801_0010` — complete scheduler request and request hash.
- `20260801_0011` — calendar, schedule, and event state constraints.
- `20260801_0012` — complete canonical occurrence document persistence.
- `20260802_0013` — optimistic household-plan lifecycle and append-only plan events.
- `20260802_0014` — append-only user-confirmed task execution events.
- `20260802_0015` — immutable repair proposals and proposal events.
- `20260802_0016` — exact target-calendar and semantic repair identity.
- `20260802_0017` — immutable proposal acceptance and repair-derived schedule provenance.
- `20260802_0018` — one accepted replacement per source schedule/version.

## Reviewed resource calendars

A calendar belongs to one household and declares version, horizon, timezone, resources, integer capacities, non-overlapping availability windows, review state, canonical UTC review time, reviewer, notes, content hash, creator, request fingerprint, idempotency key, active state, and predecessor.

Only reviewed calendars can be active. Activating a successor deactivates its predecessor and atomically invalidates dependent draft or approved schedules.

The protected Calendar Builder provides structured resource/window editing, duplicate/overlap/horizon validation, deterministic normalization, predecessor diff, canonical import/export, mandatory confirmations, and owner-only activation. Importing a draft never activates a calendar.

## Multi-window scheduling semantics

Every task must fit entirely inside one continuous containing window for every demanded resource. It cannot bridge an unavailable gap. Multi-resource tasks require simultaneous interval and cumulative-capacity feasibility.

The deterministic heuristic and bounded exact comparator share window, capacity, dependency, deadline, normalization, and utilization semantics.

## Approved source-plan prerequisite

A source-linked schedule may be created only when:

- source plan ID/version are supplied together;
- the plan belongs to the route household;
- the exact optimistic version still matches;
- the plan remains `approved`.

Plan cancellation releases active reservations and invalidates every linked schedule still in `draft` or `approved`. Household serialization guarantees that cancellation and schedule creation cannot leave a live schedule linked to a cancelled plan.

## Canonical occurrence and profile provenance

Schedule creation requires a canonical `PreparationOccurrenceSetDocument` with household identity, occurrence-set version, duration policy, occurrence IDs, recipe IDs, deadlines, servings, and priorities.

Each compiled task must match reviewed preparation-profile provenance: occurrence/recipe IDs, servings, priority, deadline, profile ID/version/hash, duration range/policy, template ID, and operational metadata. Missing, extra, or contradictory provenance fails closed.

## Persisted deterministic schedule creation

Creation accepts the active reviewed calendar, optional exact approved source plan, complete occurrence document, normalized profile map, complete scheduler request/response, notes, and idempotency key.

The server locks household scope, validates calendar/plan/occurrence/profile identity, replays deterministic scheduling, requires exact response equality and no unresolved tasks, persists all payloads/hashes, and appends `created` in the same transaction.

The combined schedule hash binds calendar, source plan, occurrence document, profile versions, request, response, and derivation identity.

## Schedule lifecycle

Statuses:

- `draft`;
- `approved`;
- `invalidated`;
- `completed`;
- `cancelled`.

Transitions:

- draft → approved;
- draft → invalidated or cancelled;
- approved → completed, invalidated, or cancelled.

Every transition requires expected version, nonblank reason, metadata, and idempotency key. Exact retries return the original result; contradictory key reuse fails. Invalidated, completed, and cancelled schedules are terminal.

### Approval authority

Owner approval revalidates calendar, source plan, occurrence/profile provenance, request/response hashes, and deterministic replay.

Original drafts use `deterministic_dependency_aware_resource_scheduler_v2`. Repair-derived drafts use `deterministic_minimal_change_preparation_repair_v1` and additionally require exact proposal, acceptance, source, acknowledgement, target-calendar, and repair-hash evidence.

### Lowest-layer completion authority

The exported `backend.services.preparation_operations_service.transition_schedule` is the lowest authoritative schedule transition.

For every valid new `approved → completed` request it:

1. preserves exact retry, contradictory-key, missing-resource, optimistic-version, and invalid-transition precedence;
2. holds household transaction/advisory and schedule row locks;
3. reconstructs deterministic tasks and append-only execution history;
4. requires every task to be explicitly `completed` or `skipped`;
5. rejects nonterminal work with `schedule_tasks_not_terminal` and sorted remaining task IDs;
6. delegates the final status mutation, version increment, event append, commit, and exact retry semantics to the preserved implementation.

`complete_schedule_with_execution_guard` is a compatibility-named delegate only. It has no independent lock, terminality proof, event append, or commit path. Product modules are statically forbidden from importing the preserved implementation directly.

A real PostgreSQL race proves schedule completion cannot commit ahead of the final task event. Completion fails with `schedule_tasks_not_terminal` if it locks first or `schedule_version_conflict` if the final event commits first; it succeeds only after retrying with the new version.

## Append-only task execution ledger

Executable task IDs and planned timing come only from the persisted deterministic response. Unknown/duplicate task IDs, incomplete schedules, or schedules with no deterministic tasks fail closed.

Task states:

- `planned`;
- `in_progress`;
- `completed`;
- `skipped`.

Allowed events:

- `started`: planned → in progress;
- `completed`: in progress → completed;
- `skipped`: planned or in progress → skipped.

Completion requires an explicit start and cannot precede it. A task cannot start until every dependency is explicitly completed or skipped. Skips and nonzero timing deviations require a nonblank reason.

Every task event requires the current schedule version, increments it exactly once, stores before/after versions, has a canonical fingerprint/idempotency key, returns the existing event on exact retry, and serializes through the same household lock as schedule transitions. Task events do not change schedule status.

## Task-execution eligibility

Viewer-authorized preflight:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/task-execution-eligibility`

Reason partition:

- `eligible`;
- `schedule_not_approved`;
- `source_schedule_has_accepted_replacement`.

A source with an accepted replacement remains readable historical evidence but cannot receive new task events or completion. The response exposes exact proposal, acceptance, replacement schedule, replacement status, and replacement version.

The protected execution workspace disables controls while eligibility is loading or false and reasserts eligibility immediately before submission. Backend mutation guards remain authoritative.

## Deterministic repair and proposal lifecycle

Advisory repair compares a complete source schedule with a revised strict request and returns preserved/moved/added/removed/unresolved outcomes plus canonical hashes. Computation permanently reports `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false`.

Proposal creation is server-recomputed and persists review evidence only. It binds exact source schedule/version/hash/request, target calendar, source plan, occurrence/profile provenance, repair request/result, revised request, repaired response, and required changed-task acknowledgements.

Acceptance requires exact evidence and creates exactly one new `draft`; it never mutates the source or performs approval/execution/completion. Migration `0018` permits multiple advisory proposals but only one accepted replacement per source schedule/version.

## Owner-only proposal invalidation

Only an owner can invalidate a still-`proposed` record. The request requires expected version, reason, `acknowledge_historical_only=true`, metadata, and idempotency key.

The server recomputes observed stale reasons and appends one immutable `invalidated` event explicitly recording no acceptance, schedule persistence, approval, or execution. It creates no schedule and permanently prevents later acceptance.

The protected Proposal Invalidation workspace presents exact source/repair evidence, stale reasons, destructive confirmation, append-only events, live no-schedule-created feedback, and editor/viewer read-only behavior.

## Schedule derivation evidence

Per-schedule derivation and household coverage endpoints distinguish original schedules from accepted repair-derived schedules and cross-check proposal, acceptance, source, target calendar, acknowledgement, method, and hash evidence.

The protected derivation inspector shows explicit denominators, original/repair counts, acceptance-link coverage, incomplete-chain warnings, identities, and hashes without lifecycle mutation.

## Frontend routes

- `/household/plans` — plan review, approval, cancellation, and events;
- `/household/plans/occurrences` — explicit approved-plan occurrence confirmation;
- `/preparation/operations` — final persistence and schedule review;
- `/preparation/operations/repair` — advisory repair review;
- `/preparation/operations/repair-proposals` — proposal creation, acceptance, rejection, and events;
- `/preparation/operations/repair-proposals/invalidation` — owner-only historical withdrawal;
- `/preparation/operations/execution` — explicit task execution and terminal completion;
- `/preparation/operations/derivation` — derivation evidence and household coverage;
- `/preparation/operations/calendars/new` — reviewed calendar builder;
- `/preparation/operations/coverage` — separate provenance and execution denominators.

Nothing is persisted, accepted, approved, executed, completed, or invalidated merely by loading a page.

## Coverage and interpretation

Operations coverage reports calendar/schedule totals, lifecycle/replay states, occurrence/request provenance, task-state counts, terminality, task-event history, deviations, skips/reasons, invalid histories, and explicit denominators.

Derivation coverage separately reports original/repair methods, complete/incomplete chains, accepted proposals, acceptance records, repaired draft/approved counts, execution-history counts, and coverage ratios.

These metrics establish record presence and structural consistency only. They do not prove cooking occurred, entries are accurate, nutrition is correct, appliances are safe, temperatures are compliant, contamination is absent, or food is safe.

## PostgreSQL concurrency evidence

Configured real PostgreSQL probes cover:

- exact duplicate and competing proposal acceptance;
- acceptance versus rejection;
- two proposals competing for one source version;
- acceptance versus proposal invalidation;
- acceptance versus source task start;
- final task completion versus schedule completion;
- duplicate/competing owner approval;
- exact migration and dialect assertions.

## Deliberate limitations

- Plan approval is household confirmation, not clinical or nutritional certification.
- Availability is declared, not inferred.
- Execution events are user-entered claims; the system does not observe execution.
- Temperature, contamination, equipment condition, and safe food state are not verified.
- Ordinary repair abstains after source task history begins; execution-aware repair remains future work.
- Joint meal, inventory, shopping, leftover, reservation, and preparation repair remains future work.
- Authenticated PostgreSQL-backed browser and automated accessibility evidence remain incomplete.
- Hosted workflow runs must be inspected before the current `main` commit is described as green.
