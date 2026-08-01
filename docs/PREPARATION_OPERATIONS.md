# Persisted Preparation Operations

NutriFlavorOS persists preparation calendars and schedules as an explicit,
human-reviewed household operations workflow. This subsystem does not control
appliances, start cooking, infer household availability, or claim that a
schedule guarantees safety or successful preparation.

## Immutable resource-calendar versions

A calendar version belongs to one household and declares:

- a stable calendar version identifier;
- horizon and timezone;
- one or more named resources;
- resource kind and integer capacity;
- one or more explicit, non-overlapping availability windows per resource;
- review status, reviewer, review time, notes, and SHA-256 content hash;
- creator, creation request fingerprint, idempotency key, active state, and
  optional superseded predecessor.

Only a reviewed calendar can become active. At most one active reviewed
calendar exists per household. Activating a successor deactivates the prior
calendar and atomically invalidates every draft or approved schedule linked to
the predecessor. Historical calendar content is never rewritten.

## Multi-window scheduling contract

The preparation scheduler accepts either the legacy one-piece interval or an
explicit list of availability windows. These forms cannot be mixed. Explicit
windows are sorted, must not overlap, and must remain inside the scheduling
horizon.

A task using a resource must fit completely inside one window for that
resource. A task cannot bridge a calendar gap, including two adjacent windows.
When a task requires multiple resources, its full interval must fit one window
of every required resource and satisfy cumulative capacity on each.

Utilization is measured against the sum of declared available minutes times
capacity, not against the entire wall-clock horizon. The heuristic and bounded
exact comparator use the same window-normalization and containment contract.

## Persisted schedule creation

A persisted schedule request carries:

1. exact active reviewed calendar version ID;
2. optional source household-plan ID and optimistic plan version;
3. occurrence-set version and SHA-256 hash;
4. preparation-profile version map;
5. complete scheduling request;
6. complete deterministic scheduling response;
7. notes and an idempotency key.

The server reconstructs resources from the immutable calendar, requires an
exact resource match, verifies source-plan ownership/version when supplied,
replays the deterministic scheduler, and accepts only a byte-equivalent model
response with no unresolved tasks. The persisted record retains the calendar
hash, occurrence hash, profile versions, schedule payload, schedule hash,
creator, optimistic version, and lifecycle status.

Client-supplied schedules are therefore never trusted without deterministic
server replay.

## Lifecycle and authorization

Statuses are:

- `draft`;
- `approved`;
- `invalidated`;
- `completed`;
- `cancelled`.

Allowed transitions are:

- draft → approved;
- draft → invalidated or cancelled;
- approved → completed, invalidated, or cancelled.

Invalidated, completed, and cancelled schedules are terminal. Every mutation
uses an expected optimistic version and an idempotency key. Identical retries
return the prior result; contradictory key reuse fails.

Roles:

- owner: register calendars, approve schedules, manually invalidate schedules;
- editor: create draft schedules, complete or cancel eligible schedules;
- viewer: read calendars, schedules, and events.

Unauthorized and cross-household requests return `404` to avoid disclosing
resource existence.

## Append-only events

Every schedule begins with a `created` event. Approval, invalidation,
completion, and cancellation each append one event containing:

- schedule and household IDs;
- actor;
- previous and new statuses;
- reason and metadata;
- idempotency key;
- request fingerprint;
- creation time.

Calendar supersession emits deterministic internal invalidation events for all
affected schedules in the same transaction.

## Database contract

Migration `20260801_0009` adds:

- `resource_calendar_versions`;
- `household_preparation_resources`;
- `persisted_preparation_schedules`;
- `preparation_schedule_events`.

Foreign keys preserve provenance. Calendars referenced by schedules and source
plans referenced by schedules use deletion restriction. Household deletion
cascades household-owned operations data. Evidence creators, approvers, and
event actors are restricted from deletion while referenced.

## Deliberate limitations

- Calendar review is a household governance action, not third-party safety
  certification.
- Availability is entered explicitly; it is not inferred from calendars,
  presence sensors, or behavior.
- Schedule approval is human confirmation, not autonomous execution.
- The system does not verify that a person followed a task, that equipment was
  safe, or that food reached a safe state.
- Calendar and plan changes invalidate dependent work but do not automatically
  regenerate or approve replacements.
- Real-time notifications, timers, appliance integrations, and execution
  telemetry remain future, separately reviewed capabilities.
