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

The client must provide expected proposal/source versions, exact source schedule/request hashes, the exact active reviewed target calendar hash, exact repair/revised-request/repaired-response hashes, the complete changed-task acknowledgement set, nonblank reason, `acknowledge_creates_new_draft_only = true`, idempotency key, and optional metadata.

Acknowledged task IDs must exactly equal the proposal’s sorted union of moved, added, removed, and unresolved tasks. Missing and unexpected IDs both fail closed.

## Transactional validation

Acceptance locks the household, proposal, source schedule, active reviewed target calendar, and acceptance state. It verifies:

- proposal remains `proposed` at the expected version;
- every supplied and persisted hash agrees;
- source schedule identity, request, status, and execution boundary are unchanged;
- no different proposal already accepted a replacement for the source version;
- source plan remains the exact approved version when linked;
- target calendar remains the exact active reviewed version;
- occurrence/profile/request/response provenance validates;
- repair previous request/response exactly match the source;
- revised request exactly matches the calendar;
- method-aware replay exactly reproduces the complete proposal result.

Any mismatch returns a stable `409` and performs no persistence.

## One accepted replacement per source version

Migration `20260802_0018` adds a unique constraint on `(source_schedule_id, source_schedule_version)`.

- Multiple advisory proposals may exist for one source version.
- Exactly one proposal may create its accepted replacement draft.
- Exact retry of the winning acceptance returns the same immutable evidence.
- A competing proposal or different key fails with `repair_source_already_has_accepted_replacement` and exposes the winning proposal, acceptance, and replacement IDs.
- Migration preflight refuses conflicting historical rows.
- Database uniqueness prevents lower-level bypass.

## New repaired draft

Acceptance creates one new schedule with:

- `status = draft` and `version = 1`;
- no approval actor/time and no task history;
- exact source plan, occurrence, profile, calendar, revised-request, and repaired-response provenance;
- `derivation_method = deterministic_minimal_change_preparation_repair_v1`;
- exact proposal/version and repair hashes;
- a derivation-bound combined schedule hash.

The source schedule is never updated or deleted.

## Immutable acceptance evidence and events

`preparation_repair_proposal_acceptances` records household/proposal identity, proposal versions, source schedule identity/hashes, created draft identity/hash, calendar and repair hashes, method, acknowledged tasks, actor, reason, metadata, idempotency key, request fingerprint, and UTC time.

One acceptance transaction appends:

1. proposal `accepted`;
2. schedule `created` for the new draft.

Both explicitly record that persistence occurred while approval and execution did not.

## Exact idempotency

- Exact retry returns the existing acceptance and draft.
- Contradictory key reuse fails.
- A different key for the same accepted proposal fails with the existing draft identity.
- A different proposal for the same source version fails with the winning source-level identity.
- Locks, fingerprints, and uniqueness serialize concurrent duplicates and competitors.

## Source plan cancellation races

A source plan cancellation, repair acceptance, and repaired owner approval serialize through the same household row lock.

Cancellation is the dominant final household state:

- the source plan ends `cancelled` at its next version;
- every linked schedule still `draft` or `approved` is invalidated atomically;
- no linked schedule remains live.

### Acceptance ordering

1. **source plan cancellation first** — source invalidation/version change or plan approval/version failure blocks acceptance and no replacement is created;
2. **acceptance first** — the accepted replacement is created, then cancellation invalidates both source and accepted replacement in the cancellation transaction.

### Owner approval ordering

1. **cancellation first** — the accepted draft is invalidated and owner approval fails by lifecycle/version/source-plan evidence;
2. **owner approval first** — the draft’s `approved` event remains immutable intermediate evidence, then cancellation invalidates both source and approved replacement.

In every ordering the final plan is cancelled, source and replacement are invalidated where present, acceptance evidence remains historical when already committed, and the count of live linked schedules is zero.

## Calendar supersession races

Calendar supersession, repair acceptance, and repaired owner approval also serialize through the household lock.

Activating a successor always leaves:

- the old calendar inactive;
- the successor active and reviewed;
- every old-calendar schedule still `draft` or `approved` invalidated;
- zero live schedules tied to the superseded calendar.

### Acceptance ordering

1. **calendar supersession first** — source invalidation and loss of the exact active reviewed target calendar block acceptance;
2. **acceptance first** — the accepted replacement is created against the old calendar, then supersession invalidates source and accepted replacement.

### Owner approval ordering

1. **supersession first** — the accepted draft is invalidated and approval fails by lifecycle/version/calendar/source evidence;
2. **owner approval first** — `approved` remains an append-only intermediate event, followed by `invalidated` when the successor activates.

In every ordering the repaired draft ends invalidated on the old calendar and no old-calendar draft or approved schedule remains live.

## Method-aware owner approval

The approval endpoint dispatches by persisted derivation method. Original drafts retain original deterministic replay. Repair-derived drafts require exact proposal/acceptance linkage, source identity and no execution history, active calendar, approved source plan, occurrence/profile provenance, acknowledged tasks, hashes, method-aware replay, and combined schedule hash.

A repaired draft invalidated by source plan cancellation or calendar supersession cannot be approved because its lifecycle status and dependency evidence no longer qualify.

## Source execution after acceptance

Once a replacement is accepted:

- the source remains readable historical evidence;
- no new source task may start, complete, or skip;
- the source cannot be completed;
- forbidden mutation returns `source_schedule_has_accepted_replacement` with exact replacement-chain identities;
- the replacement remains non-executable while draft;
- only separately owner-approved replacement may become execution eligible.

Frontend eligibility is explanatory preflight; backend mutation guards remain authoritative.

## Lost-response recovery

Real PostgreSQL probes implement **lost-response recovery** for acceptance, proposal invalidation, and schedule completion:

1. execute the service in one committed session;
2. deliberately discard the returned response;
3. close the session;
4. issue an exact retry from a fresh session using the same idempotency key and payload;
5. verify the original acceptance/draft, invalidation event, or completed schedule is returned;
6. verify no duplicate acceptance row, replacement draft, invalidation event, or completion event exists.

This models an application/client that cannot determine whether a committed response was received. It does not simulate a network disconnect, connection loss during commit, statement timeout, deadlock, or database failover. Those remain separate operational tests.

## API

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept`
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance`
- owner schedule approval remains separate;
- source plan cancellation and calendar activation remain separate actions;
- task execution and completion remain schedule actions.

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
- deterministic replay/hash failures.

Approval failures include proposal/acceptance mismatch, missing evidence, stale source, source execution, stale calendar, unapproved/stale source plan, invalid lifecycle/version, derivation mismatch, and replay/hash mismatch.

## PostgreSQL concurrency and recovery coverage

Configured real PostgreSQL probes include:

- exact duplicate and competing acceptance keys;
- acceptance versus rejection;
- acceptance versus proposal invalidation;
- rejection versus proposal invalidation;
- two proposals competing for one source version;
- acceptance versus source task start;
- source plan cancellation versus acceptance and owner approval;
- calendar supersession versus acceptance and owner approval;
- final task completion versus schedule completion;
- duplicate/competing owner approval;
- lost-response exact retry recovery for acceptance, invalidation, and completion;
- exact migration-head and PostgreSQL-dialect assertions.

Final plan, calendar, proposal, acceptance, schedule, task/schedule event, version, hash, status, and structured-error evidence is retained in JUnit artifacts. Configuration is not reported as green until the exact hosted run is observed.

## Non-claims

Acceptance means only that an authorized household member reviewed the proposal and created a new draft. It does not establish owner approval, actual task execution, human presence, appliance state, temperature/contamination status, food safety, clinical/nutritional validity, global repair optimality, actual network-failure recovery, or green hosted workflows without observed runs.
