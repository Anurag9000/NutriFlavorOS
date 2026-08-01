# Persisted Preparation Operations

NutriFlavorOS persists preparation calendars and schedules as an explicit,
human-reviewed household workflow. This subsystem does not control appliances,
start cooking, infer presence, verify that tasks occurred, or claim that a
schedule guarantees food safety or successful preparation.

## Migration history

- `20260801_0009` creates immutable resource calendars, household preparation
  resources, persisted schedules, and append-only schedule events.
- `20260801_0010` adds complete schedule-request payload and request-hash
  persistence so approval can reproduce the exact deterministic input.
- `20260801_0011` adds database constraints for calendar review state, schedule
  approval/invalidation state, valid event/status transition pairs, and nonblank
  lifecycle reasons.

The current migration head is `20260801_0011`.

## Immutable resource-calendar versions

A calendar version belongs to one household and declares:

- a stable version identifier;
- scheduling horizon and timezone;
- one or more named resources;
- resource kind and integer capacity;
- one or more explicit, non-overlapping availability windows per resource;
- review status, canonical UTC review time, reviewer, notes, and SHA-256 content
  hash;
- creator, request fingerprint, idempotency key, active state, and optional
  predecessor.

Only reviewed calendars can be active. At most one active reviewed calendar
exists per household. Equivalent UTC timestamps produce the same canonical
content and request fingerprints.

Activating a successor deactivates the previous calendar and atomically
invalidates every draft or approved schedule linked to it. Historical calendar
content is never rewritten.

The database independently rejects:

- active draft calendars;
- reviewed calendars without reviewer or review time;
- more than one active reviewed calendar per household.

## Multi-window scheduling contract

A resource may declare either the legacy continuous interval or an explicit
window list. The forms cannot be mixed. Windows are sorted, non-overlapping,
and bounded by the scheduling horizon.

A task must fit completely inside one window for every demanded resource. It
cannot bridge a gap or cross the boundary between adjacent windows. For
multi-resource tasks, one interval must be simultaneously contained by a
window for each resource and satisfy cumulative capacity on each.

Utilization uses declared available capacity-minutes, not the entire wall-clock
horizon. The deterministic heuristic and bounded exact comparator share the
same normalization, containment, dependency, deadline, and capacity contract.

## Persisted schedule creation

A creation request carries:

1. exact active reviewed calendar ID;
2. optional source household-plan ID and optimistic plan version;
3. occurrence-set version and SHA-256 hash;
4. normalized preparation-profile version map;
5. complete deterministic scheduling request;
6. complete deterministic scheduling response;
7. optional notes and an idempotency key.

The service:

1. locks the household operation key;
2. verifies the calendar belongs to the household and is the active reviewed
   version;
3. reconstructs resources from that immutable calendar;
4. requires the request resources to match exactly;
5. verifies source-plan household ownership and version when supplied;
6. replays the deterministic scheduler;
7. requires an exact response match and zero unresolved tasks;
8. stores request and response payloads;
9. stores request, calendar, occurrence, profile, plan, and combined schedule
   provenance;
10. appends a `created` event in the same transaction.

The combined schedule hash binds:

- calendar content hash;
- optional plan ID/version;
- occurrence-set version/hash;
- sorted profile versions;
- complete scheduling request;
- complete scheduling response.

Client-supplied schedules are therefore never trusted without server replay.

## Approval-time replay integrity

Approval repeats the integrity proof under the household lock:

- parse the stored request and response through current strict contracts;
- recompute and compare the request hash;
- verify the linked calendar still exists and matches its captured hash;
- require the stored request resources to match that calendar;
- replay the scheduler;
- require the replay to equal the stored response;
- reject unresolved tasks;
- recompute and compare the combined schedule hash;
- only then apply the optimistic draft-to-approved transition.

Tampered request, response, calendar provenance, or combined hashes fail with
explicit conflict codes.

### Legacy `0009` rows

Rows created before request persistence remain readable and are labeled
`legacy_request_missing`. Approval fails closed because the original input
cannot be reconstructed from the response alone.

An exact retry of the original creation request may backfill request payload and
hash. This is safe only because the original creation fingerprint already binds
the same actor, calendar, occurrence set, profile versions, request, response,
notes, and idempotency key. Contradictory reuse still fails.

## Lifecycle and authorization

Statuses:

- `draft`;
- `approved`;
- `invalidated`;
- `completed`;
- `cancelled`.

Allowed transitions:

- draft → approved;
- draft → invalidated or cancelled;
- approved → completed, invalidated, or cancelled.

Invalidated, completed, and cancelled schedules are terminal. Every mutation
uses an expected optimistic version, reason, metadata, and idempotency key.
Identical retries return the current schedule; contradictory key reuse fails.

Roles:

- owner: register calendars, approve, and manually invalidate;
- editor or owner: persist drafts, complete, or cancel eligible schedules;
- viewer/editor/owner: read calendars, schedules, and event history.

Unauthorized and cross-household requests return `404`.

The database independently enforces:

- approved/completed schedules require approver identity and time;
- invalidated schedules require invalidation time and nonblank reason;
- non-invalidated schedules cannot retain invalidation fields;
- source plan ID/version must be both present or both absent;
- replay request payload/hash must be both present or both absent;
- positive optimistic versions and 64-character hashes.

## Append-only schedule events

Every schedule begins with `created`. Approval, invalidation, completion, and
cancellation each append an event containing:

- schedule and household IDs;
- actor;
- previous and new status;
- reason and metadata;
- idempotency key;
- request fingerprint;
- creation time.

The database requires event/action pairs to match the declared transition:
created `none→draft`, approved `draft→approved`, completed
`approved→completed`, cancelled `draft|approved→cancelled`, and invalidated
`draft|approved→invalidated`. Reasons cannot be blank.

Calendar supersession appends deterministic internal invalidation events for all
affected schedules in the same transaction.

## PostgreSQL concurrency guarantees

The preparation-operations probe covers:

1. two identical calendar registrations collapse to one active record;
2. two identical schedule creations collapse to one draft and one created event;
3. approval and cancellation with the same expected version have one winner;
4. calendar supersession racing approval always leaves the predecessor schedule
   invalidated and the successor calendar active.

These guarantees rely on household row/advisory locking, optimistic schedule
versions, idempotency constraints, and active-reviewed partial uniqueness.

## API and frontend contract

Authenticated APIs are under:

`/api/v1/households/{household_id}/preparation-operations`

They expose calendar create/list/get; schedule create/list/get; approve,
complete, cancel, and invalidate; and schedule event history.

API `0.7.0` and OpenAPI contract `2026-08-01.4` require these paths,
authentication, methods, and provenance schemas. The TypeScript client has a
separate `2026-08-01.1` binding contract that checks exact top-level fields,
enums, route fragments, and HTTP methods against generated OpenAPI.

The protected `/preparation/operations` workspace provides:

- household selection and role display;
- active/historical calendar views;
- owner registration of reviewed multi-window calendars;
- replayable schedule bundle ingestion;
- request/calendar/schedule hashes and replay state;
- task timing;
- owner/editor lifecycle controls;
- explicit legacy approval warnings;
- append-only event history.

JSON ingestion is an interim audited bridge from the reviewed preparation
pipeline. A direct typed export/import handoff and structured calendar editor
remain planned.

## Foreign-key and deletion behavior

- Household deletion cascades household-owned operation rows.
- Resources cascade with their calendar.
- Schedules restrict deletion of referenced calendars and source plans.
- Evidence creators, approvers, and event actors are restricted from deletion
  while referenced.
- Schedule events cascade with their schedule.

## Deliberate limitations

- Household review is not third-party safety certification.
- Availability is explicit input, not inferred from external calendars,
  sensors, or behavior.
- Approval is human confirmation, not autonomous execution.
- The system cannot verify task completion, equipment condition, temperatures,
  contamination, or safe food state.
- Calendar/plan changes invalidate dependent work but do not generate or approve
  replacements automatically.
- Timers, reminders, checklists, presence sensors, appliance integrations, and
  execution telemetry require separate review and implementation.
