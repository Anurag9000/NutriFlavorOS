# Accepted Preparation Repair Draft Lifecycle

## Purpose

A repair proposal is immutable review evidence. Acceptance is a separate authenticated action that creates exactly one new preparation schedule in `draft` state after exact changed-task acknowledgement and deterministic method-aware replay.

Acceptance does not approve, execute, complete, mutate pantry or reservations, or make food-safety claims. Owner approval remains a different endpoint and action. The source schedule is never updated or deleted. No step implies a later step.

## Lifecycle

1. Compute advisory repair.
2. Persist a complete immutable proposal.
3. Review every moved, added, removed, and unresolved task.
4. Accept the proposal and create one new draft.
5. Owner separately approves after method-aware replay.
6. Users separately record task execution.
7. Schedule completion separately requires explicit task terminality.

Editors and owners may accept. Viewers may inspect proposal, acceptance, derivation, lifecycle, and support evidence only.

## Exact acceptance request and validation

Acceptance requires expected proposal/source versions; exact source schedule/request, target-calendar, repair-request/result, revised-request, and repaired-response hashes; the exact changed-task acknowledgement set; a nonblank reason; `acknowledge_creates_new_draft_only=true`; metadata; and a normalized idempotency key.

The transaction locks household, proposal, source schedule, reviewed target calendar, and acceptance state. It revalidates source status and execution history, approved source plan, occurrence/profile provenance, calendar activity, all hashes, required acknowledgement IDs, one-replacement uniqueness, and method-aware replay. Any mismatch fails closed with no persistence.

## One accepted replacement and immutable evidence

Migration `20260802_0018` enforces one acceptance for each `(source_schedule_id, source_schedule_version)`. Multiple advisory proposals may coexist, but only one creates the replacement. Exact retries return the same acceptance and draft; competing proposals return `repair_source_already_has_accepted_replacement` with the winning identities.

The accepted schedule is `draft`, version 1, has no approval or task history, uses `deterministic_minimal_change_preparation_repair_v1`, and binds exact proposal, source, plan, occurrence, profile, calendar, request, response, acknowledgement, and repair hashes. One transaction appends proposal `accepted` and schedule `created` events.

## Dependency and execution boundaries

The **source plan cancellation** race and **calendar supersession** race for the active reviewed target calendar serialize with acceptance and repaired approval through the household lock. If the dependency change commits first, acceptance or approval fails. If acceptance or approval commits first, the later dependency transition invalidates every affected live source or replacement schedule while preserving intermediate evidence.

After acceptance, the source remains readable but cannot receive new task start, complete, skip, or schedule-completion actions. It returns `source_schedule_has_accepted_replacement`. The replacement is executable only after separate owner approval.

## Migration rehearsal

The PostgreSQL **migration rehearsal** creates **64 valid historical acceptances** through production services at migration `20260802_0017`, records exact IDs, versions, hashes, and event sequences, upgrades to `20260802_0018`, and verifies exact preservation and the live source/version uniqueness constraint. A deliberate lower-level bypass must be rejected and roll back without adding proposal, acceptance, schedule, or event rows.

This is synthetic historical volume, not a production snapshot or performance certification.

## Lost-response recovery

Acceptance, proposal invalidation, and schedule completion have committed-response-discard probes. A fresh session repeats the exact payload with the **same idempotency key** and must receive the original result with no duplicate row or event.

## Statement timeout and deadlock recovery

Transaction-abort SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return `database_transaction_retry_required`, HTTP 503, `Retry-After: 1`, and exact same-key guidance. PostgreSQL connection exceptions and invalidated connections return `database_commit_outcome_unknown` because commit state may be ambiguous.

There is **no automatic retry** in the HTTP server. The handler does not sleep, loop, replay, or issue a second commit. Real statement-timeout evidence produces `57014`, rolls back, and succeeds on a fresh exact retry. A real row-lock/advisory-lock cycle produces exactly one `40P01` deadlock victim and converges to one acceptance and replacement.

## Post-commit connection-loss recovery

A real PostgreSQL probe records `pg_backend_pid()`, lets guarded acceptance commit, and calls `pg_terminate_backend(:pid)` before the service refreshes or returns. The caller receives a real `OperationalError` classified as `database_commit_outcome_unknown`, `outcome_unknown=true`, `retry_safe=false`, and `automatic_retry_performed=false`.

Independent reads require exactly one acceptance, replacement schedule, proposal `accepted` event, and replacement `created` event. A fresh request with the **same idempotency key** returns the original identities without duplication.

## Checked-out pool connection recovery

A separate real PostgreSQL probe terminates a connection after checkout but before acceptance begins. SQLAlchemy marks `connection_invalidated=true`; the public classifier remains conservative with `database_commit_outcome_unknown` and `retry_safe=false`. Independent evidence proves zero mutation occurred. A fresh pooled connection with a different backend PID executes the exact request once, and another exact retry returns the original acceptance.

`pool_pre_ping=True` protects stale connections at checkout but does not conceal failure of a connection that dies after checkout.

## Repeated serialization recovery

The explicit bounded client/operator utility retries only proven-aborted transactions. It preserves one normalized idempotency key, uses finite exponential backoff, emits one observation per failure, raises on exhaustion, and never automatically retries an outcome-unknown connection.

The real `SERIALIZABLE` probe forces **three consecutive SQLSTATE `40001`** aborts by establishing a worker snapshot and committing a conflicting household-row update from another transaction. Each observation reports `retry_safe=true`, `outcome_unknown=false`, and `will_retry=true`. The **fourth exact-key attempt** commits exactly one acceptance and replacement, and a fresh exact retry returns those same identities.

The server still reports `automatic_retry_performed=false`; bounded retry is an explicit caller decision around one exact idempotent request.

## API

- `POST /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/accept`
- `GET /api/v1/households/{household_id}/preparation-operations/repair-proposals/{proposal_id}/acceptance`

Proposal invalidation, plan cancellation, calendar activation, owner approval, task execution, and schedule completion remain separate actions.

## Non-claims

Acceptance proves only authorized review and creation of a new draft. It does not prove approval, actual execution, human presence, appliance state, temperature, contamination, food safety, clinical validity, global optimality, COMMIT-acknowledgement-in-flight recovery, multi-node failover recovery, production-scale migration performance, or hosted-green status without observed exact runs and artifacts.
