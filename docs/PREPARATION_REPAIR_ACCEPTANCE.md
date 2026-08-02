# Accepted Preparation Repair Draft Lifecycle

## Purpose

A repair proposal begins as persisted review evidence. Acceptance is a separate authenticated action that creates exactly one new preparation schedule in `draft` state after exact human acknowledgement and deterministic method-aware replay.

Acceptance does not approve the draft, start or complete tasks, mutate the source schedule, alter pantry or reservations, or make any execution or food-safety claim.

## Lifecycle separation

The complete sequence is:

1. compute advisory repair;
2. persist immutable proposal;
3. review every changed task;
4. accept proposal and create one new draft;
5. owner separately approves the draft after method-aware replay;
6. users separately record task execution;
7. schedule completion remains separately guarded by task terminality.

No step implies a later step.

## Acceptance authorization

Household editors and owners may accept. Viewers may read proposal, event, and acceptance evidence but cannot accept or reject.

Owner approval remains a different endpoint and action.

## Acceptance request

The client must provide:

- expected proposal version;
- expected source schedule version;
- exact source schedule and source request hashes;
- exact active reviewed target calendar hash;
- exact repair request, repair result, revised request, and repaired response hashes;
- the complete acknowledgement task-ID set;
- a nonblank review reason;
- `acknowledge_creates_new_draft_only = true`;
- an idempotency key and optional metadata.

The acknowledgement task IDs must exactly equal the proposal’s sorted union of moved, added, removed, and unresolved tasks. Missing IDs and unexpected IDs both fail closed.

## Transactional validation

The acceptance service locks the household, proposal, source schedule, target calendar, and relevant acceptance state. It then verifies:

- proposal status is `proposed`;
- proposal version and all supplied hashes are exact;
- proposal request/result payloads still validate and match their hashes;
- source schedule version, schedule hash, request hash, and supported status are unchanged;
- no task-execution event exists for the source schedule;
- source plan remains the exact approved version when linked;
- target calendar remains the exact active reviewed version;
- source occurrence, profile, request, and response provenance still validate;
- repair request previous request/response exactly match the source schedule;
- revised request exactly matches the target calendar;
- deterministic repair replay exactly reproduces the proposal result and response;
- repaired response remains complete.

Any mismatch returns a stable `409` and performs no persistence.

## New repaired draft

Acceptance creates a new `persisted_preparation_schedules` row with:

- `status = draft`;
- `version = 1`;
- no approval actor or approval time;
- no task-execution history;
- exact source plan, occurrence document, profile versions, calendar, revised request, and repaired response;
- `derivation_method = deterministic_minimal_change_preparation_repair_v1`;
- source repair proposal ID and accepted proposal version;
- repair request/result/revised-request/repaired-response hashes;
- a combined schedule hash that binds the ordinary schedule hash to the derivation method and proposal evidence.

The source schedule is never updated or deleted.

## Immutable acceptance evidence

`preparation_repair_proposal_acceptances` records:

- household and proposal identity;
- proposal version before and after acceptance;
- source schedule ID/version and hashes;
- created draft ID/version;
- exact target calendar and repair hashes;
- derivation method;
- exact acknowledged task IDs;
- actor, reason, metadata, idempotency key, request fingerprint, and UTC creation time.

There is one acceptance per proposal and one acceptance per created schedule.

## Append-only events

The transaction appends:

1. a proposal `accepted` event from `proposed` to `accepted`;
2. a schedule `created` event for the new draft.

Both events retain proposal, source, calendar, repair, and schedule identities. They explicitly state:

- schedule persistence occurred;
- approval did not occur;
- execution did not occur.

## Exact idempotency

Acceptance is unique by household and idempotency key.

- Exact retry returns the existing acceptance and draft.
- Reusing a key with different content fails.
- Accepting the same proposal under a different key fails and returns the already-created draft identity.
- Concurrent duplicates are resolved by database uniqueness and request fingerprints.

## Method-aware owner approval

The ordinary approval endpoint dispatches by persisted derivation method.

### Original drafts

Original scheduler drafts retain the established original deterministic replay path.

### Repair-derived drafts

Before owner approval, the service revalidates:

- exact accepted proposal and acceptance link;
- exact source schedule and absence of execution history;
- target calendar and source plan;
- occurrence/profile/request/response provenance;
- schedule derivation fields and hashes;
- exact acknowledgement evidence;
- complete deterministic repair replay;
- derivation-bound combined schedule hash.

Only then may the schedule transition from `draft` to `approved`.

## API

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept`
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance`
- existing owner schedule approval endpoint remains separate.

## Failure boundaries

Representative acceptance failures include:

- `repair_acceptance_idempotency_conflict`;
- `repair_proposal_already_accepted`;
- `repair_proposal_not_acceptable`;
- `repair_acceptance_identity_mismatch`;
- `repair_acceptance_acknowledgement_mismatch`;
- `repair_acceptance_source_has_execution_history`;
- `repair_acceptance_calendar_stale`;
- `repair_acceptance_previous_schedule_mismatch`;
- deterministic replay hash or output failures.

Representative repaired-draft approval failures include:

- missing or contradictory proposal/acceptance links;
- `repair_schedule_derivation_mismatch`;
- `repair_schedule_source_stale`;
- `repair_schedule_source_has_execution_history`;
- request, result, occurrence, response, or combined-hash mismatch;
- unknown derivation method.

## Non-claims

Acceptance means only that an authorized household member explicitly reviewed the proposal and created a new draft. It does not establish:

- owner approval;
- task execution;
- human presence;
- appliance state;
- temperature or contamination status;
- food safety;
- clinical or nutritional validity;
- global repair optimality;
- green hosted workflows without observed runs.
