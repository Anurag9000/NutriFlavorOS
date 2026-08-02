# Persisted Preparation Operations

NutriFlavorOS persists preparation calendars and schedules as an explicit, human-reviewed household workflow. It does not control appliances, infer presence, verify execution, or guarantee food safety or successful preparation.

## Migration and contract history

- `20260801_0009` — immutable resource calendars, resources, schedules, and events.
- `20260801_0010` — complete scheduler request and request hash.
- `20260801_0011` — calendar/schedule/event state constraints.
- `20260801_0012` — complete canonical occurrence document persistence.
- `20260802_0013` — optimistic household-plan lifecycle and append-only plan events.

Current boundary:

- migration head `20260802_0013`;
- API `0.9.0`;
- OpenAPI contract `2026-08-02.3`;
- preparation bindings `2026-08-02.2`;
- household-plan bindings `2026-08-02.3`.

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

A new plan is initially `draft`. Owner approval increments its version and records actor/time and an append-only plan event. The schedule must retain the approved version, not the original draft version.

Rejection codes include:

- `source_plan_not_approved`;
- `source_plan_version_mismatch`.

If plan cancellation races schedule creation, the shared household row lock and internal version recheck guarantee one of two outcomes:

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

- occurrence/recipe IDs;
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
5. verify active reviewed calendar identity/hash/resources;
6. recheck source-plan household/version;
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

Roles:

- owner: calendar registration, schedule approval/invalidation, plan approval;
- editor/owner: schedule persistence/completion/cancellation and plan cancellation;
- viewer/editor/owner: calendars, schedules, plan records, coverage, and events.

Cross-household or unauthorized access returns `404`.

## Append-only evidence

Schedule events retain actor, from/to state, reason, metadata, idempotency, fingerprint, and time. Database constraints permit only valid event/state pairs.

Household plan events retain equivalent transition provenance for approval and cancellation. Schedule invalidations caused by plan cancellation include source-plan ID/version and cancellation reason.

## Legacy schedules

Replay state is explicit:

- `replayable`;
- `legacy_request_missing`;
- `legacy_occurrence_set_missing`.

Legacy rows remain readable but cannot be approved. An exact creation retry may backfill missing replay/occurrence payloads only when stored identity and hashes match.

## Provenance coverage

`GET /api/v1/households/{household_id}/preparation-operations/coverage` reports exact household denominators for calendars, schedule states, replay states, occurrence documents, scheduler requests, complete replay provenance, source-plan linkage, and append-only events.

Coverage proves record presence, not correctness, freshness, execution, nutrition quality, appliance condition, or food safety.

## Concurrency evidence

Configured PostgreSQL probes cover:

- identical calendar retries;
- identical schedule retries;
- competing schedule approval/cancellation;
- calendar supersession versus approval;
- identical plan approval retries;
- competing plan approval/cancellation.

Plan cancellation and schedule creation share household serialization and exact version rechecks.

## Frontend routes

- `/household/plans` — exact plan review, approval, cancellation, and events;
- `/preparation/operations` — calendars, schedules, hashes, replay state, transitions, and schedule events;
- `/preparation/operations/calendars/new` — structured reviewed calendar builder;
- `/preparation/operations/coverage` — provenance denominators and warnings.

`preparation-operations-handoff-v2` transfers occurrence, profile, optional plan, resource, request, and deterministic response data without automatic persistence or approval.

## Deliberate limitations

- Plan approval is household confirmation, not clinical or nutritional certification.
- Availability is declared, not inferred.
- Execution is not observed.
- Temperature, contamination, equipment condition, and safe food state are not verified.
- Plan/calendar changes invalidate dependent work but do not create or approve replacements.
- Approved-plan occurrence generation, structured schedule review, per-task execution events, timers/reminders, and joint repair remain incomplete.
- Presence sensors, appliance integrations, autonomous procurement, and control remain disabled pending separate validation and governance.
