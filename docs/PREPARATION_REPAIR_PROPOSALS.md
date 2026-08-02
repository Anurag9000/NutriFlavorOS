# Immutable Preparation Repair Proposals

## Purpose

A repair proposal is a persisted, hash-addressed review record created from a server-recomputed deterministic preparation repair. It preserves the exact source schedule, source request, target reviewed calendar, revised request, repair result, outcome ledger, and human-review requirements.

A proposal is **not** an accepted schedule. It does not replace the source schedule, create a new draft, approve work, create task-execution evidence, complete work, or decide food safety.

Every API view reports:

- `accepted = false`;
- `schedule_persistence_performed = false`.

The nested repair result independently reports:

- `requires_human_acceptance = true`;
- `accepted = false`;
- `persistence_performed = false`.

## Creation contract

An editor or owner supplies:

- source schedule ID and expected optimistic version;
- exact target reviewed calendar version;
- revised strict scheduling request;
- immutable task IDs;
- repair strategy and bounded-search settings;
- explicit acknowledgement that computation is neither acceptance nor persistence;
- notes and an idempotency key.

The server does not trust a client-provided repair result. It:

1. locks the household and source schedule;
2. verifies the exact source version and supported source state;
3. validates the complete persisted occurrence document, source request, deterministic response, and request hash;
4. verifies any source plan is still the exact approved version;
5. locks and verifies the active reviewed target calendar;
6. requires revised resources and horizon to match that calendar exactly;
7. recomputes repair with `allow_partial = false`;
8. rejects incomplete repair;
9. validates the revised task metadata against retained occurrence/profile provenance;
10. computes canonical SHA-256 hashes for the repair request and result;
11. persists only the proposal and a creation event.

The source schedule remains unchanged.

## Exact idempotency

Proposal creation is unique by `(household_id, creation_idempotency_key)` and binds that key to a full request fingerprint including household, actor, and strict payload.

- An exact retry returns the existing proposal.
- Reusing the key with different content returns `409`.
- Distinct idempotency keys create distinct review records, even when their semantic repair hashes match.

Semantic source/calendar/request/response hashes are indexed evidence, not a replacement for exact request-key idempotency. This avoids silently aliasing a second key that was never durably reserved.

Proposal events are independently idempotent by `(proposal_id, idempotency_key)`.

## Persisted identity and hashes

Each proposal retains:

- household ID;
- source schedule ID, version, schedule hash, and source request hash;
- target calendar version ID and content hash;
- strict repair request payload and hash;
- strict repair result payload and hash;
- revised request hash;
- repaired response hash;
- required acknowledgement task IDs;
- actor, notes, status, optimistic version, and timestamps.

The required acknowledgement set is the sorted union of moved, added, removed, and unresolved tasks.

## Status and events

Current proposal states are:

- `proposed`;
- `rejected`;
- `invalidated` reserved for future server-authoritative invalidation transitions.

Current events are:

- `created`;
- `rejected`;
- `invalidated` reserved for future transition tooling.

Creation starts at proposal version `1`. Rejection is an editor/owner action from `proposed` to `rejected`, increments the optimistic version, requires a nonblank reason, and appends one immutable event. Exact retry returns the same result; stale versions and contradictory event-key reuse fail closed.

## Staleness

Reads compute whether a proposal remains current without mutating history. Stale reasons include:

- proposal no longer in `proposed` state;
- source schedule missing, version changed, hash changed, request hash changed, or unsupported status;
- source plan no longer the exact approved version;
- target calendar missing, hash changed, inactive, or no longer reviewed.

A stale proposal remains readable as historical evidence but cannot be represented as current or accepted.

## Authorization and non-disclosure

Household viewers may list, read, and inspect events. Editors and owners may create and reject proposals. Household access uses the same role and `404` non-disclosure rules as other preparation operations.

API surface:

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/events`;
- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/reject`.

There is deliberately no accept, approve, persist, complete, or execute endpoint.

## Tamper detection

Proposal reads revalidate the strict nested repair result, recompute its canonical hash, and verify the revised-request and repaired-response hashes match the proposal columns. Invalid payloads or hash mismatches return structured `409` errors.

## Why accepted-draft persistence is still blocked

Existing persisted schedule approval replays the original deterministic scheduler. A repair response uses a distinct deterministic repair method. Creating a repaired draft before method-aware replay exists would create a record that cannot pass the existing approval replay contract.

Accepted-draft persistence therefore remains blocked until all of the following are implemented together:

- method-aware replay for original and repaired schedules;
- explicit acknowledgement of every required changed task;
- stale source/calendar/plan/evidence revalidation at acceptance time;
- exact acceptance idempotency and PostgreSQL concurrency behavior;
- append-only accepted-draft evidence;
- a new draft preserving source proposal and all hashes;
- separate owner approval and task execution.

## Verification

The proposal contract validator checks:

- migration head and required runtime tables;
- ORM/Alembic idempotency, status, event, index, and hash contracts;
- generated authenticated OpenAPI paths;
- absence of accept/approve/persist/complete proposal endpoints;
- server recomputation and complete-only repair;
- exact request-key idempotency rather than cross-key semantic aliasing;
- no call to persisted-schedule creation or lifecycle/execution mutation;
- required service and API regression tests.

Focused tests cover server recomputation, hashes, non-acceptance, exact retries, contradictory reuse, distinct-key review records, stale source versions, provenance drift, calendar supersession, staleness, rejection, append-only events, and tamper failure.

## Non-claims

A proposal does not establish:

- acceptance or approval;
- a persisted replacement schedule;
- task execution or human presence;
- appliance or sensor state;
- temperature or contamination evidence;
- food safety;
- clinical or nutrition validation;
- global repair optimality;
- hosted green-build evidence without an observed exact workflow run.
