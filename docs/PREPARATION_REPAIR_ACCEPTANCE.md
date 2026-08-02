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

Acceptance locks the household, proposal, source schedule, active reviewed target calendar, and acceptance state. It verifies:

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

`preparation_repair_proposal_acceptances` records household/proposal identity, proposal versions, source schedule identity/hashes, created draft identity/hash, target calendar and repair hashes, derivation method, exact acknowledged tasks, actor, reason, metadata, idempotency key, request fingerprint, and UTC time.

There is one acceptance per proposal, one per created schedule, and one per source schedule/version.

## Append-only events

One acceptance transaction appends:

1. a proposal `accepted` event;
2. a schedule `created` event for the new draft.

Both retain proposal, source, calendar, repair, and schedule identities and explicitly state that schedule persistence occurred while approval and execution did not.

## Exact idempotency

- Exact retry returns the existing acceptance and draft.
- Reusing a key with different content fails.
- Accepting the same proposal under another key fails and returns the existing draft identity.
- Accepting another proposal for the same source version fails with the source-level winning identity.
- Concurrent duplicates and competitors are resolved by locks, uniqueness, and fingerprints.

## Source plan cancellation race

A source plan cancellation and repair acceptance serialize through the same household row lock.

Cancellation is the dominant final household state:

- cancellation always leaves the source plan `cancelled` at its next optimistic version;
- every linked source schedule still `draft` or `approved` is invalidated atomically;
- no linked schedule remains live after cancellation.

Two valid race orders exist:

1. **source plan cancellation first** — the source schedule is invalidated and its version changes; acceptance fails closed with source identity/status or source-plan approval/version evidence and creates no replacement;
2. **acceptance first** — acceptance creates its accepted replacement draft, then cancellation invalidates both the original source and the newly accepted replacement in the same cancellation transaction.

The accepted proposal and immutable acceptance record remain historical evidence when acceptance committed first, but the replacement is not left executable or approvable. PostgreSQL assertions retain final plan state, source/replacement schedule states, proposal/acceptance rows, schedule invalidation events, plan event metadata, and a zero count of live linked schedules.

## Calendar supersession race

Calendar supersession and repair acceptance also serialize through the household lock.

Activating a successor calendar always leaves:

- the old target calendar inactive;
- the successor active and reviewed;
- every old-calendar schedule still `draft` or `approved` invalidated;
- zero live schedules tied to the superseded calendar.

Two valid race orders exist:

1. **calendar supersession first** — the source is invalidated and the target is no longer the exact active reviewed target calendar; acceptance fails closed and creates no replacement;
2. **acceptance first** — acceptance creates its accepted replacement draft against the old calendar, then supersession invalidates both source and replacement atomically.

The PostgreSQL probe retains old/successor calendar identities and hashes, proposal/acceptance evidence, source/replacement schedule states, invalidation events, and the zero-live-old-calendar invariant.

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

A repaired draft invalidated by source plan cancellation or calendar supersession cannot be approved because its lifecycle status and dependency evidence no longer qualify.

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
- owner schedule approval remains separate;
- source plan cancellation and calendar activation remain their own household/preparation endpoints;
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
- `repair_acceptance_source_status_changed`;
- `repair_acceptance_calendar_stale`;
- `source_plan_not_approved`;
- `source_plan_version_mismatch`;
- `repair_acceptance_previous_schedule_mismatch`;
- deterministic replay hash/output failures.

Approval failures include missing or contradictory proposal/acceptance links, acceptance mismatch, derivation mismatch, stale source, source execution history, lifecycle invalidation, request/result/occurrence/response/combined-hash mismatch, and unknown derivation method.

## PostgreSQL concurrency coverage

Configured real PostgreSQL probes include:

- exact duplicate acceptance;
- competing acceptance keys;
- acceptance versus rejection;
- acceptance versus proposal invalidation;
- rejection versus proposal invalidation;
- two proposals competing for one source version;
- acceptance versus source task start;
- source plan cancellation versus acceptance;
- calendar supersession versus acceptance;
- final task completion versus schedule completion;
- duplicate/competing owner approval;
- exact migration-head and PostgreSQL-dialect assertions.

Final plan, calendar, proposal, acceptance, schedule, task/schedule event, version, hash, status, and structured-error evidence is retained in JUnit artifacts. Configuration is not reported as green until the exact hosted run is observed.

## Non-claims

Acceptance means only that an authorized household member reviewed the proposal and created a new draft. It does not establish owner approval, task execution, human presence, appliance state, temperature or contamination status, food safety, clinical/nutritional validity, global repair optimality, or green hosted workflows without observed runs.
