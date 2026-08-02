# Immutable Preparation Repair Proposals

## Purpose

A repair proposal is a persisted, hash-addressed human-review record created from a server-recomputed deterministic preparation repair. It preserves the exact source schedule, source request, target reviewed calendar, revised request, repair result, outcome ledger, and required changed-task acknowledgements.

Proposal creation never implies acceptance. It does not replace the source schedule, create a new draft, approve work, create task-execution evidence, complete work, or decide food safety.

The nested repair computation permanently reports:

- `requires_human_acceptance = true`;
- `accepted = false`;
- `persistence_performed = false`.

Those computation fields never change after later proposal acceptance. Proposal lifecycle fields separately report whether a new draft was created.

## Creation contract

An editor or owner supplies:

- source schedule ID and expected optimistic version;
- exact target reviewed calendar version;
- revised strict scheduling request;
- immutable task IDs;
- repair strategy and bounded-search settings;
- explicit acknowledgement that proposal creation is neither acceptance nor persistence;
- notes and an idempotency key.

The server does not trust a client-provided repair result. It:

1. locks the household and source schedule;
2. verifies exact source version, hash, request hash, status, and replay provenance;
3. rejects any source with task-execution history;
4. verifies the exact approved source plan when present;
5. locks and verifies the active reviewed target calendar;
6. requires revised resources and horizon to match that calendar exactly;
7. recomputes repair with `allow_partial = false`;
8. rejects incomplete repair;
9. validates revised task metadata against occurrence/profile provenance;
10. computes canonical SHA-256 request/result hashes;
11. derives the sorted acknowledgement set from moved, added, removed, and unresolved tasks;
12. persists only the proposal and a creation event.

The source schedule remains unchanged.

## Exact creation idempotency

Proposal creation is unique by `(household_id, creation_idempotency_key)` and binds that key to a full request fingerprint including household, actor, and strict payload.

- An exact retry returns the existing proposal.
- Reusing the key with different content returns `409`.
- Distinct keys create distinct advisory review records even when semantic repair hashes match.

Semantic source/calendar/request/response hashes are indexed evidence, not a replacement for exact request-key idempotency.

## Persisted identity and hashes

Each proposal retains:

- household ID;
- source schedule ID/version/hash and source request hash;
- target calendar ID and content hash;
- strict repair request payload/hash;
- strict repair result payload/hash;
- revised request hash;
- repaired response hash;
- required acknowledgement task IDs;
- actor, notes, status, optimistic version, and timestamps;
- rejection or acceptance evidence when the corresponding transition occurs.

## Lifecycle

Proposal states are:

- `proposed`;
- `accepted`;
- `rejected`;
- `invalidated` reserved for server-authoritative invalidation tooling.

Proposal events are:

- `created`;
- `accepted`;
- `rejected`;
- `invalidated`.

Creation starts at proposal version `1`.

### Rejection

An editor or owner may reject a current proposal. Rejection requires the expected proposal version, nonblank reason, metadata, and idempotency key. It increments the version and appends one immutable event. Exact retries collapse; stale versions and contradictory key reuse fail closed.

### Acceptance

Acceptance creates a new draft. It is a distinct editor/owner action and requires:

- exact expected proposal version;
- exact source schedule version/hash and request hash;
- exact target calendar content hash;
- exact repair request/result/revised-request/repaired-response hashes;
- acknowledgement of every required changed task, with no missing or extra IDs;
- a nonblank reason;
- explicit confirmation that only a draft will be created;
- exact idempotency key and metadata.

At acceptance time the server re-locks and revalidates the household, proposal, source schedule, source plan, target calendar, occurrence/profile provenance, task-execution boundary, and every retained hash. It performs method-aware repair replay and requires a complete deterministic match.

If valid, one transaction:

1. creates exactly one new schedule in `draft` state and version `1`;
2. binds the draft to the repair derivation method and all proposal hashes;
3. computes a combined schedule hash that includes derivation identity;
4. records immutable acceptance evidence;
5. transitions the proposal from `proposed` to `accepted`;
6. appends proposal `accepted` and schedule `created` events.

The source schedule is never updated or deleted.

Acceptance does not approve, execute, complete, cancel, or invalidate the new draft.

## One accepted replacement per source schedule version

Migration `20260802_0018` enforces one accepted replacement per source schedule version using a unique constraint on `(source_schedule_id, source_schedule_version)`.

- Multiple advisory proposals may exist for one source version.
- Only one proposal may create the accepted replacement draft.
- Exact retry of the winning acceptance is idempotent.
- A competing proposal or distinct acceptance key receives `repair_source_already_has_accepted_replacement` and the winning proposal, acceptance, and replacement schedule identities.
- Migration preflight refuses to add the constraint if conflicting historical acceptance rows already exist.
- The database constraint prevents direct lower-level service use from bypassing the invariant.

## Separate owner approval

Owner approval remains a different endpoint and action. A repaired draft cannot use the original-scheduler-only replay path.

Before approval the system locks and cross-checks:

- repaired draft and derivation method;
- source proposal and immutable acceptance record;
- exact acknowledged-task set;
- source schedule identity and absence of execution history;
- target reviewed calendar;
- approved source plan;
- occurrence/profile provenance;
- every repair and schedule hash.

It then performs a second method-aware replay. Only an exact match may transition the draft to `approved` and append a schedule approval event.

No step implies a later step: proposal creation does not imply acceptance; acceptance does not imply approval; approval does not imply execution; task events do not imply schedule completion.

## Execution boundary after acceptance

After a source version has an accepted replacement:

- the source remains readable historical evidence;
- no new source task may start, complete, or skip;
- the source cannot be completed;
- forbidden mutations return `source_schedule_has_accepted_replacement` with exact proposal, acceptance, and replacement identities;
- the replacement remains non-executable while `draft`;
- only the separately owner-approved replacement may become task-execution eligible.

The viewer-authorized eligibility endpoint and protected execution workspace surface this boundary before mutation, while the backend replacement guard remains authoritative.

## Staleness and tamper detection

Before acceptance, proposal reads compute whether the evidence remains current without mutating history. Reasons include:

- proposal no longer `proposed`;
- source missing, version/hash/request changed, status unsupported, or execution history present;
- source plan no longer the exact approved version;
- target calendar missing, changed, inactive, or no longer reviewed.

Reads revalidate the nested repair payload and all canonical hashes. Acceptance and approval independently repeat exact cross-record checks. Invalid payloads, contradictory identities, or tampered evidence return structured `409` errors.

## Authorization and non-disclosure

- Viewers may list/read proposals, proposal events, and acceptance evidence.
- Editors and owners may create, accept, or reject proposals.
- Only owners may approve the resulting draft.
- Household access uses the same role and `404` non-disclosure rules as other preparation operations.

API surface:

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/events`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance`;
- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept`;
- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/reject`.

Approval, task execution, and schedule completion remain schedule endpoints, not proposal shortcuts.

## Frontend

The protected Repair Proposals workspace provides:

- advisory proposal creation with non-acceptance/non-persistence confirmations;
- exact source/calendar/request/hash evidence;
- outcome and changed-task review;
- exact acknowledgement checkboxes;
- draft-only acceptance confirmation and reason;
- immutable acceptance/draft evidence;
- explicit link to separate owner approval;
- versioned rejection;
- append-only proposal events;
- viewer read-only behavior and stale-proposal blocking.

The workspace does not expose proposal-side approval, task execution, or completion controls and does not use browser storage to bypass server authority.

## Verification

Configured verification covers:

- migrations `0015` through `0018` and runtime schema head;
- ORM uniqueness, status, event, index, hash, and derivation contracts;
- generated authenticated OpenAPI paths and schemas;
- server recomputation and complete-only proposals;
- exact creation, acceptance, and rejection idempotency;
- one-replacement-per-source enforcement at guard and database layers;
- changed-task acknowledgement mismatch;
- source/calendar/plan/provenance/execution staleness;
- method-aware replay and owner approval;
- source immutability and one-new-draft-only persistence;
- cross-record tamper rejection;
- PostgreSQL acceptance, rejection, source-execution, and approval races;
- protected frontend creation/acceptance/rejection behavior.

Configured workflows are not reported as green until the exact current hosted run and retained artifacts are observed.

## Non-claims

A proposal, acceptance, or approved schedule does not establish:

- actual task execution or human presence;
- appliance or sensor state;
- temperature or contamination evidence;
- food safety;
- clinical or nutrition validation;
- global repair optimality;
- current hosted green-build status without observed evidence.
