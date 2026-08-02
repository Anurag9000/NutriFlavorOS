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

An editor or owner supplies the exact source schedule/version, target reviewed calendar, revised strict request, immutable task IDs, strategy, explicit non-acceptance/non-persistence acknowledgements, notes, and an idempotency key.

The server:

1. locks the household and source schedule;
2. verifies exact source version, hash, request hash, status, and replay provenance;
3. rejects any source with task-execution history;
4. verifies the exact approved source plan when present;
5. locks and verifies the active reviewed target calendar;
6. requires revised resources and horizon to match that calendar;
7. recomputes complete repair server-side;
8. validates revised task metadata against occurrence/profile provenance;
9. computes canonical request/result hashes;
10. derives the sorted acknowledgement set from moved, added, removed, and unresolved tasks;
11. persists only the proposal and creation event.

The source schedule remains unchanged.

## Exact creation idempotency

Proposal creation is unique by `(household_id, creation_idempotency_key)` and binds the key to a full request fingerprint.

- Exact retry returns the existing proposal.
- Contradictory reuse returns `409`.
- Distinct keys create distinct advisory review records even when semantic hashes match.

Semantic hashes remain indexed evidence, not a substitute for request-key idempotency.

## Persisted identity

Each proposal retains household, source schedule/version/hash/request hash, target calendar ID/hash, strict repair request/result payloads and hashes, revised-request hash, repaired-response hash, required acknowledgement task IDs, actor, notes, status, optimistic version, and timestamps.

## Lifecycle states and events

States:

- `proposed`;
- `accepted`;
- `rejected`;
- `invalidated`.

Events:

- `created`;
- `accepted`;
- `rejected`;
- `invalidated`.

Creation starts at proposal version `1`.

### Rejection

An editor or owner may reject a proposed record. Rejection requires expected version, nonblank reason, metadata, and idempotency key. It increments the version and appends an immutable event. Exact retries collapse; stale versions and contradictory keys fail closed.

### Acceptance

Acceptance creates a new draft. It is a distinct editor/owner action requiring:

- exact expected proposal version;
- exact source schedule version/hash/request hash;
- exact target calendar hash;
- exact repair request/result/revised-request/repaired-response hashes;
- acknowledgement of every required changed task, with no missing or extra IDs;
- nonblank reason;
- explicit confirmation that only a draft will be created;
- exact idempotency key and metadata.

The route calls the source-version acceptance guard before the lower-level acceptance service. At acceptance time the system re-locks and revalidates the proposal, source, source plan, calendar, occurrence/profile provenance, task-execution boundary, and every hash, then performs method-aware replay.

One transaction creates exactly one new `draft`, records immutable acceptance evidence, transitions the proposal to `accepted`, and appends proposal and schedule events. It never mutates the source or performs approval/execution/completion.

### Owner-only proposal invalidation

An owner may explicitly withdraw a `proposed` record from all future acceptance by calling the invalidation endpoint.

The request requires:

- exact expected proposal version;
- nonblank reason;
- `acknowledge_historical_only = true`;
- exact idempotency key;
- optional metadata.

The server locks the household and proposal, recomputes the **observed stale reasons**, and appends one `invalidated` event. The event records:

- observed stale reasons at invalidation time;
- `historical_only = true`;
- `accepted = false`;
- `schedule_persistence_performed = false`;
- `approval_performed = false`;
- `execution_performed = false`.

Invalidation does not reuse rejection fields, create a schedule, alter the source, or imply that the proposal was necessarily stale. It may withdraw current evidence or formally close already-stale evidence. Exact retry returns the same terminal record; contradictory key reuse, stale versions, and attempts to invalidate accepted/rejected/invalidated proposals fail closed.

Editors may create, accept, or reject proposals but cannot invalidate them. Owner authority is enforced by the household route before the service runs.

## One accepted replacement per source schedule version

Migration `20260802_0018` enforces one accepted replacement for `(source_schedule_id, source_schedule_version)`.

- Multiple advisory proposals may exist for one source version.
- Only one may create the accepted replacement draft.
- Exact retry of the winner is idempotent.
- A competing proposal/key receives `repair_source_already_has_accepted_replacement` with winning proposal, acceptance, and replacement IDs.
- Migration preflight refuses conflicting historical rows.
- The database constraint prevents lower-level bypass.

## Separate owner approval

Owner approval remains a different schedule action. Repaired-draft approval locks and cross-checks the draft, proposal, acceptance, acknowledgement set, source identity/history, calendar, plan, occurrence/profile provenance, and every repair/schedule hash before a second method-aware replay.

No step implies a later step: creation does not imply acceptance; acceptance does not imply approval; approval does not imply execution; task events do not imply schedule completion.

## Execution boundary after acceptance

After a source version has an accepted replacement:

- the source remains readable history;
- no new source task may start, complete, or skip;
- the source cannot be completed;
- forbidden mutations return `source_schedule_has_accepted_replacement` with exact replacement-chain identities;
- the replacement remains non-executable while draft;
- only the separately owner-approved replacement may become execution eligible.

The eligibility endpoint and protected execution workspace surface this before mutation; the backend guard remains authoritative.

## Staleness and tamper detection

Before terminal transition, reads recompute whether proposal evidence remains current. Reasons include changed/missing source, source execution history, unapproved source plan, and changed/inactive/unreviewed target calendar.

Reads revalidate nested repair payloads and canonical hashes. Acceptance, invalidation, and approval independently enforce optimistic state and append-only evidence. Tampered or contradictory data returns structured `409` errors.

## Authorization and API

- Viewers may list/read proposals, events, and acceptance evidence.
- Editors and owners may create, accept, or reject.
- Only owners may invalidate proposals and approve resulting drafts.
- Household non-disclosure returns `404` outside the authorized scope.

API surface:

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/events`;
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance`;
- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept`;
- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/reject`;
- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/invalidate`.

Approval, execution, and completion remain schedule endpoints, not proposal shortcuts.

## Frontend

The protected Repair Proposals workspace provides advisory creation, exact evidence, outcome review, changed-task acknowledgement, draft-only acceptance, immutable acceptance evidence, separate approval navigation, rejection, events, viewer read-only behavior, and stale-proposal blocking.

The typed client includes owner invalidation support, but the current primary workspace does not yet expose an invalidation control; owner administrative UI remains a follow-on item. The API and append-only events are authoritative.

## Verification

Configured verification covers migrations `0015`–`0018`, runtime head, ORM constraints, generated OpenAPI, server recomputation, exact creation/acceptance/rejection/invalidation idempotency, source-version uniqueness, owner authorization, stale-reason capture, zero schedule persistence, source immutability, method-aware approval, execution boundaries, tamper rejection, PostgreSQL races, and protected frontend review.

Configured workflows are not reported green until the exact current hosted run and artifacts are observed.

## Non-claims

A proposal, invalidation, acceptance, or approved schedule does not establish actual execution, human presence, appliance/sensor state, temperature/contamination evidence, food safety, clinical validity, global optimality, or current hosted green-build status.
