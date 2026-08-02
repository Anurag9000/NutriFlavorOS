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

## Authorization

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

Acknowledged task IDs must exactly equal the proposal’s sorted union of moved, added, removed, and unresolved tasks. Missing and unexpected IDs both fail closed.

## Transactional validation

Acceptance locks the household, proposal, source schedule, target calendar, and acceptance state. It verifies:

- proposal status is `proposed`;
- proposal version and all supplied hashes are exact;
- proposal request/result payloads still validate and match their hashes;
- source schedule version, schedule hash, request hash, and supported status are unchanged;
- no task-execution event exists for the source;
- no different proposal already accepted a replacement for the same source version;
- source plan remains the exact approved version when linked;
- target calendar remains the exact active reviewed version;
- occurrence/profile/request/response provenance still validates;
- repair request previous request/response exactly match the source;
- revised request exactly matches the target calendar;
- deterministic repair replay exactly reproduces the proposal result and response;
- repaired response remains complete.

Any mismatch returns a stable `409` and performs no persistence.

## One accepted replacement per source version

Migration `20260802_0018` adds a unique constraint on `(source_schedule_id, source_schedule_version)`.

- Multiple advisory proposals may exist for one source version.
- Exactly one proposal may create its accepted replacement draft.
- Exact retry of the winning acceptance returns the same immutable evidence.
- A competing proposal or different acceptance key fails with `repair_source_already_has_accepted_replacement`.
- The conflict includes the winning proposal, acceptance, and replacement schedule IDs.
- Migration preflight refuses to add the constraint when conflicting historical rows exist.
- The database prevents direct lower-level acceptance calls from bypassing the guard.

## New repaired draft

Acceptance creates a new `persisted_preparation_schedules` row with:

- `status = draft`;
- `version = 1`;
- no approval actor/time;
- no task-execution history;
- exact source plan, occurrence document, profile versions, calendar, revised request, and repaired response;
- `derivation_method = deterministic_minimal_change_preparation_repair_v1`;
- source proposal ID and accepted proposal version;
- repair request/result/revised-request/repaired-response hashes;
- a combined schedule hash binding ordinary schedule identity to derivation evidence.

The source schedule is never updated or deleted.

## Immutable acceptance evidence

`preparation_repair_proposal_acceptances` records:

- household and proposal identity;
- proposal version before/after acceptance;
- source schedule ID/version and hashes;
- created draft ID/version/hash;
- target calendar and repair hashes;
- derivation method;
- exact acknowledged task IDs;
- actor, reason, metadata, idempotency key, request fingerprint, and UTC time.

There is one acceptance per proposal, one per created schedule, and one per source schedule/version.

## Append-only events

One acceptance transaction appends:

1. a proposal `accepted` event;
2. a schedule `created` event for the new draft.

Both retain proposal, source, calendar, repair, and schedule identities and explicitly state:

- schedule persistence occurred;
- approval did not occur;
- execution did not occur.

## Exact idempotency

- Exact retry returns the existing acceptance and draft.
- Reusing a key with different content fails.
- Accepting the same proposal under another key fails and returns the existing draft identity.
- Accepting another proposal for the same source version fails with the source-level winning identity.
- Concurrent duplicates and competitors are resolved by locks, uniqueness, and fingerprints.

## Method-aware owner approval

The ordinary approval endpoint dispatches by persisted derivation method.

### Original drafts

Original scheduler drafts retain the original deterministic replay path.

### Repair-derived drafts

Before owner approval, the system revalidates:

- exact accepted proposal and acceptance link;
- exact source schedule and absence of execution history;
- target calendar and source plan;
- occurrence/profile/request/response provenance;
- schedule derivation fields and hashes;
- exact acknowledgement evidence;
- complete deterministic repair replay;
- derivation-bound combined schedule hash.

A locked acceptance guard checks the acceptance record itself against proposal, source, created draft, method, hashes, and acknowledgement set. Only then may the schedule transition from `draft` to `approved`.

## Source execution after acceptance

Once a replacement is accepted:

- the source remains readable historical evidence;
- no new source task may start, complete, or skip;
- the source cannot be completed;
- a forbidden mutation returns `source_schedule_has_accepted_replacement` with exact proposal, acceptance, and replacement identities;
- the replacement remains non-executable while draft;
- the separately owner-approved replacement may become execution eligible.

The viewer-authorized task-execution eligibility endpoint reports this state before frontend controls are enabled. The backend replacement guard remains authoritative.

## API

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept`
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance`
- the existing owner schedule approval endpoint remains separate;
- task-execution eligibility and mutations remain schedule endpoints.

## Representative failure boundaries

Acceptance failures include:

- `repair_acceptance_idempotency_conflict`;
- `repair_proposal_already_accepted`;
- `repair_source_already_has_accepted_replacement`;
- `repair_proposal_not_acceptable`;
- `repair_acceptance_identity_mismatch`;
- `repair_acceptance_acknowledgement_mismatch`;
- `repair_acceptance_source_has_execution_history`;
- `repair_acceptance_calendar_stale`;
- `repair_acceptance_previous_schedule_mismatch`;
- deterministic replay hash/output failures.

Approval failures include:

- missing or contradictory proposal/acceptance links;
- `repair_approval_acceptance_mismatch`;
- `repair_schedule_derivation_mismatch`;
- `repair_schedule_source_stale`;
- `repair_schedule_source_has_execution_history`;
- request/result/occurrence/response/combined-hash mismatch;
- unknown derivation method.

## PostgreSQL concurrency coverage

Configured PostgreSQL probes include:

- exact duplicate acceptance;
- competing acceptance keys;
- acceptance versus rejection;
- two proposals competing for one source version;
- acceptance versus source task start;
- duplicate/competing owner approval;
- exact migration-head and PostgreSQL-dialect assertions.

Final proposal, acceptance, schedule, and event evidence is retained in JUnit artifacts. Configuration is not reported as green until the exact hosted run is observed.

## Non-claims

Acceptance means only that an authorized household member reviewed the proposal and created a new draft. It does not establish:

- owner approval;
- task execution or human presence;
- appliance state;
- temperature or contamination status;
- food safety;
- clinical or nutritional validity;
- global repair optimality;
- green hosted workflows without observed runs.
