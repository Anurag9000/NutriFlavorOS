# Accepted Preparation Repair Draft Lifecycle

## Purpose

A repair proposal begins as persisted review evidence. Acceptance is a separate authenticated action that creates exactly one new preparation schedule in `draft` state after exact human acknowledgement and deterministic method-aware replay.

Acceptance does not approve the draft, start or complete tasks, mutate the source schedule, alter pantry or reservations, or make any execution or food-safety claim.

## Lifecycle separation

The sequence is:

1. compute advisory repair;
2. persist immutable proposal;
3. review every changed task;
4. accept proposal and create one new draft;
5. owner separately approves after method-aware replay;
6. users separately record task execution;
7. schedule completion remains guarded by explicit task terminality.

No step implies a later step.

## Authorization and request contract

Household editors and owners may accept. Viewers may read proposal, event, and acceptance evidence but cannot accept or reject. Owner approval remains a different endpoint and action.

The client supplies expected proposal/source versions; exact source schedule/request, calendar, repair, revised-request, and repaired-response hashes; the complete changed-task acknowledgement set; a nonblank reason; `acknowledge_creates_new_draft_only=true`; an idempotency key; and optional metadata.

Acknowledged task IDs must exactly equal the sorted union of moved, added, removed, and unresolved tasks. Missing or unexpected IDs fail closed.

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
- Exact retry returns the same immutable evidence.
- A competing proposal or different key fails with `repair_source_already_has_accepted_replacement` and exposes the winning identities.
- Migration preflight refuses conflicting historical rows.
- Database uniqueness prevents lower-level bypass.

## New repaired draft and immutable evidence

Acceptance creates one new schedule with `status=draft`, `version=1`, no approval actor/time, no task history, exact source plan/occurrence/profile/calendar/request/response provenance, `derivation_method=deterministic_minimal_change_preparation_repair_v1`, exact proposal/version and repair hashes, and a derivation-bound combined schedule hash.

The source schedule is never updated or deleted.

`preparation_repair_proposal_acceptances` records household/proposal identity, proposal versions, source schedule identity/hashes, created draft identity/hash, calendar and repair hashes, method, acknowledged tasks, actor, reason, metadata, idempotency key, request fingerprint, and UTC time.

One transaction appends proposal `accepted` and replacement schedule `created`. Both record that persistence occurred while approval and execution did not.

## Exact idempotency

- Exact retry returns the existing acceptance and draft.
- Contradictory key reuse fails.
- A different key for the accepted proposal fails with the existing draft identity.
- A different proposal for the same source version fails with the winning source-level identity.
- Locks, fingerprints, and uniqueness serialize duplicates and competitors.

## Source-plan cancellation and calendar-supersession races

Source-plan cancellation, target-calendar supersession, acceptance, and repaired owner approval serialize through the household lock.

If cancellation or supersession commits first, acceptance or approval fails by lifecycle, version, plan, calendar, or source evidence. If acceptance or approval commits first, the later dependency transition invalidates every affected source or replacement schedule still live. Intermediate approval/acceptance evidence remains immutable, while the final dependency state dominates and no invalid live schedule remains.

## Migration rehearsal

The dedicated PostgreSQL **Migration rehearsal** validates a populated `20260802_0017 → 20260802_0018` path.

It creates **64 valid historical acceptances** through production calendar, schedule, proposal, and guarded-acceptance services at `0017`. The manifest records exact proposal, source, replacement, acceptance, event, version, and hash identities. After upgrade, verification requires every identity/hash to remain unchanged, checks the source/version unique constraint in PostgreSQL catalogs, and requires the distinct source/version count to equal the acceptance count.

A deliberate lower-level bypass attempt must fail at the database constraint and roll back without changing proposal, acceptance, schedule, or event counts. Manifest, verification report, and JUnit evidence are retained separately.

This is synthetic historical volume, not a production snapshot, performance certification, or hosted-green claim.

## Method-aware owner approval and source execution boundary

Original drafts retain original deterministic replay. Repair-derived drafts require exact proposal/acceptance linkage, source identity and no execution history, active calendar, approved source plan, occurrence/profile provenance, acknowledgements, hashes, method-aware replay, and combined schedule hash.

Once a replacement is accepted, the source remains readable historical evidence but cannot receive new start/complete/skip events or completion. Forbidden mutation returns `source_schedule_has_accepted_replacement`. The replacement remains non-executable while draft and becomes eligible only after separate owner approval.

## Lost-response recovery

Real PostgreSQL probes implement lost-response recovery for acceptance, proposal invalidation, and schedule completion:

1. execute and commit in one session;
2. deliberately discard the returned response;
3. close the session;
4. issue an exact retry from a fresh session using the **same idempotency key** and payload;
5. require the original result;
6. require no duplicate acceptance, draft, invalidation event, or completion event.

This models a response that was not observed. It does not by itself simulate a terminated database connection.

## Statement timeout and deadlock recovery

The API installs a sanitized operational-database error boundary.

Transaction-abort SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return HTTP `503` with `database_transaction_retry_required`, `Retry-After: 1`, and direction to retry the exact request with the **same idempotency key**. PostgreSQL connection exceptions (`08xxx`) or driver-invalidated connections return `database_commit_outcome_unknown`, because commit state may be ambiguous.

There is **no automatic retry**. The handler does not sleep, loop, replay, or issue a second commit. Exact request identity, existing idempotency evidence, uniqueness, and a fresh-session retry determine the outcome.

Real evidence includes a row-lock `statement_timeout=150ms` producing SQLSTATE `57014`, rollback, and successful exact retry; and a genuine row-lock/advisory-lock cycle producing exactly one `40P01` deadlock victim followed by convergence to one immutable acceptance, one draft, and `created → accepted` proposal events.

## Post-commit connection-loss recovery

A real PostgreSQL probe now covers a terminated service backend after commit:

1. create a current repair proposal and exact acceptance payload;
2. record the worker connection’s `pg_backend_pid()`;
3. execute guarded acceptance normally;
4. after the service commits but before its first refresh/response, use an independent administrator session to call `pg_terminate_backend(:pid)`;
5. require the worker to raise a real `OperationalError`, not a fabricated exception;
6. classify it as `database_commit_outcome_unknown`, with `outcome_unknown=true`, `retry_safe=false`, and `automatic_retry_performed=false`;
7. independently read the database and require exactly one acceptance row, one repair-derived replacement schedule, one proposal `accepted` event, and one replacement schedule `created` event;
8. require the proposal to be `accepted` at exactly the next version;
9. retry from a fresh session with the exact **same idempotency key** and payload;
10. require the original acceptance and draft identities and unchanged row/event counts.

The AST-backed contract verifies that the test actually executes `SELECT pg_terminate_backend(:pid)` and forbids monkeypatched commit exceptions or fabricated `OperationalError` construction.

This proves post-commit connection-loss recovery after the database commit has completed but before response materialization. It does not yet prove behavior when the network is severed while the COMMIT acknowledgement itself is in flight, multi-node primary failover, or pool invalidation under load.

## API

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept`
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance`
- owner approval, plan cancellation, calendar activation, task execution, and schedule completion remain separate actions.

## Representative failures

Acceptance failures include idempotency conflict, already accepted, source already replaced, proposal not acceptable, identity/hash mismatch, acknowledgement mismatch, source execution/status change, calendar staleness, source-plan mismatch, previous-schedule mismatch, and deterministic replay/hash failure.

Approval failures include proposal/acceptance mismatch, missing evidence, stale source, source execution, stale calendar, unapproved/stale source plan, invalid lifecycle/version, derivation mismatch, and replay/hash mismatch.

## PostgreSQL concurrency and recovery coverage

Configured real PostgreSQL probes include duplicate/competing acceptance; acceptance versus rejection, invalidation, source task start, plan cancellation, calendar supersession, and owner approval; final task completion versus schedule completion; lost-response exact retries; statement timeout; genuine deadlock recovery; post-commit backend termination and same-key recovery; populated `0017 → 0018` migration rehearsal; and exact migration-head/dialect assertions.

Final plan, calendar, proposal, acceptance, schedule, task/schedule event, version, hash, status, SQLSTATE, migration-manifest, migration-verification, and structured-error evidence is retained in workflow artifacts. Configuration is not reported green until the exact hosted run is observed.

## Non-claims

Acceptance means only that an authorized household member reviewed the proposal and created a new draft. It does not establish owner approval, actual task execution, human presence, appliance state, temperature or contamination status, food safety, clinical or nutritional validity, global repair optimality, COMMIT-acknowledgement-in-flight recovery, failover recovery, production-scale migration performance, or hosted-green status without observed runs.
