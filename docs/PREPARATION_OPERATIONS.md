# Persisted Preparation Operations

NutriFlavorOS persists reviewed resource calendars, deterministic preparation schedules, repair evidence, accepted replacement drafts, derivation provenance, explicit household task events, and read-only support snapshots as a human-reviewed workflow. It does not control appliances, infer presence, verify cooking, measure temperature, or guarantee food safety or successful preparation.

## Current boundary

- Alembic head: `20260802_0018`
- API: `0.15.4`
- OpenAPI contract: `2026-08-03.2`
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

The ORM metadata declares the same `uq_preparation_repair_acceptance_source_version` invariant as migration `0018`, so direct metadata fixtures and migrated databases do not diverge.

## Reviewed resource calendars

A calendar belongs to one household and declares version, horizon, timezone, resources, capacities, non-overlapping windows, review state, canonical UTC review time, reviewer, notes, content hash, creator, request fingerprint, idempotency key, active state, and predecessor.

Only reviewed calendars can be active. Activating a successor deactivates its predecessor and atomically invalidates dependent draft or approved schedules. PostgreSQL races prove supersession dominates both proposal acceptance and repaired owner approval: an already-created or already-approved replacement becomes immutable historical evidence and is then invalidated on the old calendar.

## Approved source-plan prerequisite

A source-linked schedule may be created only when source plan ID/version are supplied together, belong to the route household, match the current optimistic version, and remain `approved`.

Plan cancellation releases active reservations and invalidates every linked schedule still in `draft` or `approved`. PostgreSQL races prove cancellation dominates acceptance and repaired owner approval under either lock ordering, leaving zero live linked schedules.

## Canonical occurrence and profile provenance

Schedule creation requires a canonical occurrence document with household identity, occurrence version, duration policy, occurrence/recipe IDs, deadlines, servings, and priorities.

Each task must match reviewed preparation-profile provenance: occurrence/recipe IDs, servings, priority, deadline, profile ID/version/hash, duration range/policy, template ID, and operational metadata. Missing, extra, or contradictory provenance fails closed.

## Persisted deterministic schedule creation

Creation accepts the active reviewed calendar, optional approved source plan, occurrence document, profile map, complete scheduler request/response, notes, and idempotency key.

The server locks household scope, validates all identities, replays deterministic scheduling, requires exact response equality and no unresolved tasks, persists payloads/hashes, and appends `created` in one transaction.

The combined schedule hash binds calendar, source plan, occurrence, profiles, request, response, and derivation identity.

## Schedule lifecycle and approval

Statuses are `draft`, `approved`, `invalidated`, `completed`, and `cancelled`. Terminal states are invalidated, completed, and cancelled.

Every transition requires expected version, nonblank reason, metadata, and idempotency key. Exact retries return the original result; contradictory reuse fails.

Owner approval revalidates calendar, source plan, occurrence/profile provenance, hashes, and replay. Original drafts use `deterministic_dependency_aware_resource_scheduler_v2`. Repair-derived drafts use `deterministic_minimal_change_preparation_repair_v1` and additionally require exact proposal, acceptance, source, acknowledgement, calendar, and repair evidence.

## Lowest-layer completion authority

The exported `transition_schedule` is the lowest schedule-transition authority.

For a new `approved → completed` request it preserves existing error precedence, holds household/schedule locks, reconstructs tasks and append-only execution history, requires every task to be explicitly completed or skipped, and only then delegates final mutation/event/commit to the preserved implementation.

Nonterminal work returns `schedule_tasks_not_terminal` with sorted IDs. The named completion service is a compatibility delegate only. Static validation forbids product modules from importing the preserved implementation directly.

A real PostgreSQL final-task race proves completion cannot commit ahead of the last task event. It loses with either `schedule_tasks_not_terminal` or `schedule_version_conflict`, then succeeds only at the post-event version.

## Append-only task execution

Executable task IDs and planned timing come only from the persisted deterministic response. Unknown/duplicate tasks, incomplete schedules, or missing tasks fail closed.

States are planned, in progress, completed, and skipped. Start, complete, and skip events enforce prior state, dependency chronology, completion-after-start, horizon-relative actual minutes, deviations, mandatory reasons for skips/nonzero deviations, optimistic versions, fingerprints, and exact idempotency.

Task events do not change schedule status and remain user-entered claims rather than observed execution.

## Task-execution eligibility

Viewer-authorized preflight returns exactly `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement` with proposal, acceptance, replacement schedule, replacement status, and replacement version where applicable.

The frontend disables mutation controls while eligibility is loading or false. Backend guards independently reassert eligibility.

## Deterministic repair and proposal lifecycle

Advisory repair returns preserved/moved/added/removed/unresolved outcomes plus canonical hashes and permanently reports `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false`.

Proposal creation is server-recomputed and persists review evidence only. Acceptance requires exact evidence and creates exactly one new draft; it never mutates the source or performs approval/execution/completion. Migration `0018` permits multiple advisory proposals but only one accepted replacement per source schedule/version.

Owner-only invalidation permanently withdraws a still-proposed record, appends one historical event, creates no schedule, and prevents later acceptance.

## Schedule derivation evidence

Per-schedule derivation and household coverage endpoints distinguish original schedules from accepted repair-derived schedules and cross-check proposal, acceptance, source, target calendar, acknowledgement, method, and hash evidence.

## Preparation schedule support export

Viewer-authorized endpoint:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/support-export`

The strict export includes persisted schedule and lifecycle events; derivation evidence; task-execution eligibility; deterministic task state and append-only task events; every proposal using the selected schedule as source; the source proposal when the selected schedule is a replacement; acceptance records and complete proposal event chains; one canonical SHA-256 evidence hash; and explicit `mutation_performed=false`, `actual_execution_verified=false`, and `food_safety_verified=false`.

PostgreSQL uses a dedicated `REPEATABLE READ`, `SET TRANSACTION READ ONLY` transaction and records `txid_current_snapshot()`. Hashing excludes snapshot timestamps and transaction metadata, so it represents domain evidence rather than export timing.

The request session requires viewer access and preserves `404` non-disclosure. PostgreSQL repeats viewer authorization inside the exact read-only snapshot, using only the server-derived authenticated user ID. The operator CLI remains a separate privileged path.

A concurrent-acceptance probe pauses an export after the snapshot is established, commits acceptance elsewhere, and requires the original export to retain proposed/eligible/no-acceptance evidence while a fresh export sees accepted/blocked/replacement evidence and a different hash.

## Database operational failures

Transaction-abort SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return sanitized `503` responses with `database_transaction_retry_required`, `Retry-After: 1`, and same-idempotency-key guidance. Connection exceptions and invalidated connections return `database_commit_outcome_unknown`.

`retryable=true` means an exact client retry is prescribed. `retry_safe=true` is limited to transaction-abort evidence proving rollback. Connection ambiguity remains `retry_safe=false`. No automatic server mutation retry occurs.

Real PostgreSQL probes cover statement timeout, genuine deadlock, discarded-response convergence, post-commit backend termination with exact recovery, and checked-out pool connection invalidation before mutation. The pool probe requires `connection_invalidated=true`, zero mutation before retry, a different fresh backend PID, exactly one accepted replacement afterward, and an exact second retry returning the same evidence.

## Frontend routes

- `/household/plans` — plan review, approval, cancellation, and events;
- `/household/plans/occurrences` — approved-plan occurrence confirmation;
- `/preparation/operations` — final persistence and schedule review;
- `/preparation/operations/repair` — advisory repair review;
- `/preparation/operations/repair-proposals` — proposal lifecycle;
- `/preparation/operations/repair-proposals/invalidation` — owner-only withdrawal;
- `/preparation/operations/execution` — explicit task execution and completion;
- `/preparation/operations/derivation` — derivation evidence and coverage;
- `/preparation/operations/support-export` — explicit read-only evidence generation and download;
- `/preparation/operations/calendars/new` — reviewed calendar builder;
- `/preparation/operations/coverage` — provenance and execution denominators.

Nothing is persisted, accepted, approved, executed, completed, or invalidated merely by loading a page.

## PostgreSQL evidence matrix

Configured real PostgreSQL probes cover duplicate/competing acceptance, acceptance/rejection, acceptance/invalidation, rejection/invalidation, source execution onset, plan cancellation, calendar supersession, repaired approval, final-task completion, repeatable-read support export, discarded responses, post-commit connection loss, checked-out pool invalidation, statement timeout, deadlock, populated migration rehearsal, and exact migration/dialect assertions.

## Deliberate limitations

- Plan approval is household confirmation, not clinical or nutritional certification.
- Availability is declared, not inferred.
- Execution events are user-entered claims; the system does not observe execution.
- Temperature, contamination, equipment condition, and safe food state are not verified.
- Ordinary repair abstains after source task history begins.
- Joint meal/inventory/shopping/leftover/reservation/preparation repair remains future work.
- COMMIT-acknowledgement-in-flight recovery, multi-node failover, sustained pool-load recovery, signed/encrypted support packages, retention, download audit, and production load evidence remain incomplete.
- Authenticated PostgreSQL-backed browser and automated accessibility evidence remain incomplete.
- Hosted workflow runs must be inspected before the current `main` commit is described as green.
