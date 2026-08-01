# Persisted Preparation Operations

NutriFlavorOS persists preparation calendars and schedules as an explicit, human-reviewed household workflow. This subsystem does not control appliances, start cooking, infer presence, verify that tasks occurred, or claim that a schedule guarantees food safety or successful preparation.

## Migration history

- `20260801_0009` creates immutable resource calendars, household preparation resources, persisted schedules, and append-only schedule events.
- `20260801_0010` adds complete scheduler-request payload and request-hash persistence.
- `20260801_0011` adds database constraints for calendar review state, schedule approval/invalidation state, valid event/status pairs, and nonblank lifecycle reasons.
- `20260801_0012` adds the complete canonical occurrence-set payload beside its immutable version/hash, allowing approval to verify the actual occurrence document rather than a client assertion.

The current migration head is `20260801_0012`.

## Immutable resource-calendar versions

A calendar belongs to one household and declares:

- a stable version identifier;
- scheduling horizon and timezone;
- named resources, kind, label, and integer capacity;
- one or more explicit, non-overlapping availability windows per resource;
- review status, canonical UTC review time, reviewer, notes, and SHA-256 content hash;
- creator, request fingerprint, idempotency key, active state, and optional predecessor.

Only reviewed calendars can be active. At most one active reviewed calendar exists per household. Equivalent UTC timestamps produce the same canonical content and request fingerprints.

Activating a successor deactivates the previous calendar and atomically invalidates every draft or approved schedule linked to it. Historical content is never rewritten.

## Multi-window scheduling contract

A resource may declare either a preserved legacy continuous interval or an explicit non-empty window list. The forms cannot be mixed. Explicitly empty lists fail closed rather than silently becoming full-horizon availability. Windows are sorted, non-overlapping, and bounded by the horizon.

A task must fit completely inside one declared window for every demanded resource. It cannot bridge a gap or cross adjacent-window boundaries. Multi-resource tasks need one simultaneously valid interval and sufficient cumulative capacity on every demanded resource.

Utilization uses declared available capacity-minutes, not the full wall-clock horizon. The deterministic heuristic and bounded exact comparator share normalization, containment, dependency, deadline, and capacity semantics.

## Canonical occurrence document

Schedule creation requires `PreparationOccurrenceSetDocument`:

- document version;
- household ID;
- immutable occurrence-set version;
- duration policy;
- one or more occurrences with occurrence ID, recipe ID, required finish minute, servings, and priority.

The server canonicalizes occurrence order and derives SHA-256 from the complete document. A client cannot replace the document with a self-asserted hash.

Each compiled task must carry provenance matching one occurrence:

- occurrence and recipe IDs;
- servings, priority, and deadline;
- preparation-profile ID, version, and content hash;
- reviewed duration minimum/maximum;
- selected duration policy and resulting duration;
- task-template metadata.

The profile-version map must exactly match the recipes and hashes used by tasks. Missing, extra, or contradictory provenance fails validation.

## Persisted schedule creation

A creation request carries:

1. exact active reviewed calendar ID;
2. optional source household-plan ID and optimistic plan version, supplied together;
3. complete occurrence document;
4. normalized preparation-profile version map;
5. complete deterministic scheduler request;
6. complete deterministic scheduler response;
7. optional notes and an idempotency key.

The authoritative service:

1. locks the household operation key;
2. verifies route and occurrence-document household equality;
3. verifies the selected calendar belongs to the household and is active/reviewed;
4. reconstructs resources from the immutable calendar and requires an exact request match;
5. verifies source-plan household and version when supplied;
6. validates occurrence/profile/task/duration provenance;
7. replays the deterministic scheduler;
8. requires exact response equality and zero unresolved tasks;
9. stores the occurrence document, scheduler request, deterministic response, and all hashes;
10. appends `created` in the same transaction.

The combined schedule hash binds:

- calendar content hash;
- optional plan ID/version;
- occurrence-set version/hash;
- sorted profile versions;
- complete scheduler request;
- complete deterministic response.

Client-supplied schedules are never trusted without server replay.

## Approval-time replay integrity

Approval repeats the integrity proof under the household lock:

- require a stored occurrence document and scheduler request;
- parse occurrence, request, and response through current strict contracts;
- revalidate occurrence/profile/task/duration consistency;
- recompute and compare occurrence and request hashes;
- verify the linked calendar still exists, is active/reviewed, and matches its captured hash;
- require stored request resources to match that calendar;
- verify the optional source plan and version;
- replay the scheduler and require exact response equality;
- recompute and compare the combined schedule hash;
- only then apply the optimistic draft-to-approved transition.

Tampered occurrence document, request, response, profile map, source plan, calendar provenance, or combined hash fails with explicit conflict codes.

## Legacy rows and exact backfill

Rows created before complete replay/occurrence persistence remain readable. Replay state is explicit:

- `replayable`;
- `legacy_request_missing`;
- `legacy_occurrence_set_missing`.

Legacy approval fails closed. An exact retry of the original creation request may backfill missing request and/or occurrence payloads only when the original fingerprint and stored version/hash agree. Contradictory reuse fails.

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

Invalidated, completed, and cancelled schedules are terminal. Every mutation uses an expected optimistic version, reason, metadata, and idempotency key. Identical retries return current state; contradictory reuse fails.

Roles:

- owner: register calendars, approve, and manually invalidate;
- editor or owner: persist drafts, complete, or cancel eligible schedules;
- viewer/editor/owner: read calendars, schedules, and events.

Unauthorized and cross-household requests return `404`.

## Append-only schedule events

Every schedule begins with `created`. Approval, invalidation, completion, and cancellation append an event containing schedule/household, actor, previous/new status, reason, metadata, idempotency key, request fingerprint, and creation time.

The database requires action/status consistency: created `none→draft`, approved `draft→approved`, completed `approved→completed`, cancelled `draft|approved→cancelled`, and invalidated `draft|approved→invalidated`. Reasons cannot be blank.

Calendar supersession appends deterministic internal invalidation events for all affected schedules in the same transaction.

## Concurrency guarantees

The PostgreSQL probe covers:

1. two identical calendar registrations collapse to one active record;
2. two identical schedule creations collapse to one draft and one created event;
3. approval and cancellation with the same expected version have one winner;
4. calendar supersession racing approval leaves the predecessor schedule invalidated and successor calendar active.

These guarantees rely on household row/advisory locking, optimistic versions, idempotency constraints, and active-reviewed uniqueness.

## API and frontend contract

Authenticated APIs are under:

`/api/v1/households/{household_id}/preparation-operations`

They expose calendar create/list/get; schedule create/list/get; approve, complete, cancel, invalidate; and event history.

API `0.8.0`, OpenAPI contract `2026-08-02.1`, and TypeScript binding contract `2026-08-02.1` require the occurrence-document request and provenance views.

The protected `/preparation/operations` workspace provides:

- household and role scope;
- active/historical calendars and owner registration;
- exact occurrence, request, calendar, and schedule hashes;
- replay status and explicit approval blocking;
- role-aware transitions, task timing, and append-only history.

`preparation-operations-handoff-v2` transfers the reviewed pipeline's exact occurrence document, profile map, optional plan pair, resources, compiled tasks, and deterministic response into the workspace. The browser validates task/occurrence/profile/duration consistency before storing the one-time handoff. Persistence and approval still require explicit human actions and server replay.

## Foreign-key and deletion behavior

- Household deletion cascades household-owned operation rows.
- Resources cascade with their calendar.
- Schedules restrict deletion of referenced calendars and source plans.
- Evidence creators, approvers, and event actors are restricted while referenced.
- Schedule events cascade with their schedule.

## Deliberate limitations

- Household review is not third-party safety certification.
- Availability is explicit input, not inferred from calendars, sensors, or behavior.
- Approval is human confirmation, not autonomous execution.
- The system cannot verify task completion, equipment condition, temperatures, contamination, or safe food state.
- Calendar/plan changes invalidate dependent work but do not generate or approve replacements automatically.
- Structured calendar editing, approved-plan occurrence generation, per-task execution events, timers, reminders, and joint plan/schedule repair remain future product work.
- Presence sensors, appliance integrations, execution telemetry, and autonomous procurement/control remain disabled pending separate validation and governance.
