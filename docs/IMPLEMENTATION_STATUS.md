# NutriFlavorOS Implementation Status

**Status date:** 2026-08-05  
**Development policy:** coherent direct commits to `main`; no feature pull requests or development branches; no history rewriting.  
**Database migration head:** `20260802_0018`  
**API version:** `0.15.4`  
**OpenAPI release contract:** `2026-08-03.2`  
**Food-evidence frontend binding contract:** `2026-08-01.2`  
**Preparation-operations frontend binding contract:** `2026-08-02.4`  
**Household-plan frontend binding contract:** `2026-08-02.4`  
**Effective research catalog:** `2026-08-01.3`

Governed inventory: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

Committed code, configured workflows, synthetic fixtures, and catalog rows are not by themselves readiness, clinical-validation, food-safety, execution-verification, or green-build claims.

## Core implemented platform

- Argon2 passwords, signed JWTs, weak-secret refusal, explicit profile completion, and owner/editor/viewer household roles with `404` non-disclosure.
- Transactional pantry lots, leftovers, append-only inventory events, FEFO allocation, reservations, shopping reconciliation, optimistic versions, and exact idempotency.
- Quantity-aware deterministic meal planning, persisted plan lifecycle, owner approval, cancellation consequences, optional CP-SAT/MILP, robust/exact comparators, and approved source-plan references.
- Reviewed preparation profiles and resource calendars, canonical occurrence/profile provenance, deterministic scheduling/replay, combined hashes, and persisted schedule lifecycle.
- Deterministic minimal-change repair with greedy and bounded exact methods, immutable anchors, predecessor closure, structured conflicts, authenticated API, offline CLI, and permanent advisory non-persistence.

## Repair lifecycle

### One accepted replacement per source schedule version

**One accepted replacement per source schedule version** is enforced by migration `20260802_0018`. Multiple advisory proposals may exist, but exactly one may create a replacement. Competing requests return `repair_source_already_has_accepted_replacement` and the winning proposal, acceptance, and replacement identities.

The populated migration rehearsal creates **64 valid accepted lifecycles** through production services at `0017`, upgrades to `0018`, verifies exact identities/hashes/events, checks the live constraint, and proves lower-level bypass rollback.

### Owner-only proposal invalidation

**Owner-only proposal invalidation** is implemented through an authenticated endpoint, typed client, protected administration workspace, exact version/idempotency, server-observed stale reasons, and append-only events. It creates no schedule and leaves editors/viewers read-only.

### Acceptance and approval

Acceptance creates one new draft only, never mutates the source, and requires exact changed-task acknowledgement plus method-aware replay. Owner approval remains separate and revalidates proposal, acceptance, source, plan, calendar, provenance, hashes, and replay under locks.

## Schedule and execution evidence

### Schedule derivation evidence

**Schedule derivation evidence** distinguishes original and accepted repair-derived schedules through per-schedule and household coverage endpoints and a protected inspector. It cross-checks proposal, acceptance, source, calendar, acknowledgement, method, and hashes.

### Lowest-layer task terminality

**Lowest-layer task terminality** is enforced in exported `transition_schedule`. Direct completion before explicit terminal task evidence returns `schedule_tasks_not_terminal`. A real PostgreSQL race proves schedule completion cannot commit ahead of the final task event.

### Task-execution eligibility

**Task-execution eligibility** returns `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement`. Replaced sources remain readable but cannot receive task events or completion. Frontend preflight is explanatory; backend guards remain authoritative.

## Preparation schedule support export

The viewer-authorized **Preparation schedule support export** endpoint, operator CLI, typed GET-only client, and protected browser workspace provide one strict, hash-addressed, read-only evidence package.

- PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, and `txid_current_snapshot()`.
- The request session enforces viewer access, and PostgreSQL repeats viewer authorization inside the exact evidence snapshot.
- The package binds schedule, lifecycle, derivation, eligibility, task history, proposals, acceptances, proposal events, and explicit non-claims.
- The browser provides **explicit support-evidence generation/download**, clears stale scope, restores focus, downloads complete JSON, revokes object URLs, and uses no browser storage or mutation method.
- A real concurrent-acceptance test proves historical and fresh snapshots diverge correctly without export-created rows.

## Database transient failures and exact recovery

**Database transient failures and exact recovery** distinguish client action from proven retry safety:

- `retryable=true` prescribes repeating the exact idempotent request.
- Proven-aborted SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` report `retry_safe=true`.
- Connection exceptions and invalidated connections report `database_commit_outcome_unknown` and `retry_safe=false`.
- Connection ambiguity dominates a nominal retry SQLSTATE; an invalidated `40001` remains outcome-unknown and not retry-safe.
- SQLAlchemy pool exhaustion before checkout reports `database_pool_timeout`, `no_transaction_started=true`, `retry_safe=true`, and `outcome_unknown=false`.
- The HTTP handler always reports `automatic_retry_performed=false`.

Implemented real PostgreSQL evidence includes:

- **statement-timeout evidence** with `57014`, rollback, and successful exact retry;
- **deadlock evidence** with one `40P01` victim and exact convergence;
- discarded-response exact recovery for acceptance, invalidation, and completion;
- **post-commit connection-loss evidence** using `pg_terminate_backend` after commit and exact same-key recovery;
- **checked-out pool connection invalidation evidence** with `connection_invalidated=true`, `retry_safe=false`, zero pre-recovery mutation, a different fresh backend PID, and one accepted result;
- **bounded exact serialization retry** with finite exponential backoff, immutable observations, exact-key preservation, and no replay of outcome-unknown connections;
- a genuine `SERIALIZABLE` test forcing **three consecutive `40001` aborts** before the fourth exact-key attempt creates exactly one acceptance and replacement;
- controlled **pool exhaustion** using `QueuePool(pool_size=1, max_overflow=0, pool_timeout=0.1)`, zero acceptance/schedule/event mutation before checkout recovery, and exact-key convergence to one accepted replacement;
- **controlled sustained pool pressure** using a two-connection pool, three synchronized waves, and eight callers per wave. All **24 checkout timeouts** preserve `no_transaction_started=true`, produce **zero lifecycle mutation**, exhaust only the caller’s single-attempt budget, release to `checkedout() == 0`, and then converge through the same idempotency key to one immutable accepted replacement.

### Controlled application-worker recycle

A **controlled application-worker recycle** exercises a separate subprocess while its one-connection pool is fully occupied.

- The old worker publishes a stable 32-character worker-instance identity and a live PostgreSQL backend PID.
- Its guarded acceptance receives one real `database_pool_timeout` and creates zero acceptance, schedule, or lifecycle-event rows.
- The parent requests an orderly recycle through stdin; the worker closes its held connection, reports `pool_checked_out_after_close=0`, disposes its engine, and exits successfully.
- The parent proves the **old PostgreSQL backend disappears** from `pg_stat_activity`.
- A **fresh worker process** publishes a different worker-instance identity and backend PID, accepts the same exact request once, and closes with zero checked-out connections.
- A later parent-session retry returns the same acceptance and schedule identities.

### Controlled ungraceful application-worker crash

A real **ungraceful application-worker crash** boundary now uses `SIGKILL` in two PostgreSQL subprocess cases.

- Checkout-holder crash: the worker holds the only pool connection, a guarded acceptance times out before transaction start, independent reads prove zero lifecycle mutation, and the parent kills the worker with `SIGKILL`.
- Flushed-open-transaction crash: production acceptance reaches a test-only `Session.commit()` interception, calls `flush()`, and exposes one transaction-local acceptance, replacement schedule, accepted event, and created event while independent committed readers still see zero and the proposal remains `proposed`.
- The parent sends `SIGKILL`, waits for the old PostgreSQL backend to disappear, and proves PostgreSQL rolled the **flushed but uncommitted** lifecycle back to exactly zero committed mutation.
- A fresh worker with a different worker-instance identity and backend PID repeats the same exact idempotency key, creates one accepted replacement, and closes without a pool leak.
- A later exact retry returns the same acceptance and schedule identities and preserves proposal event order `created → accepted`.

This crash boundary proves controlled process-death rollback before COMMIT. The separate COMMIT acknowledgement boundary below covers one controlled post-COMMIT ambiguity case.

### Controlled PostgreSQL COMMIT acknowledgement loss

A real **COMMIT acknowledgement loss** boundary uses a test-only PostgreSQL wire proxy around one production acceptance request.

- The proxied transaction explicitly sets `synchronous_commit=on` and verifies the effective value.
- The proxy parses both simple-query and extended-protocol frontend messages, arms the drop before forwarding the real COMMIT, and records that the complete COMMIT frame was forwarded upstream.
- PostgreSQL emits `CommandComplete(COMMIT)`; the proxy consumes that frame, withholds it from the client, and closes both proxied sockets.
- SQLAlchemy raises an invalidated `OperationalError`, classified as `database_commit_outcome_unknown`, `retry_safe=false`, `outcome_unknown=true`, and `automatic_retry_performed=false`.
- Independent direct reads observe exactly one acceptance, one draft replacement schedule, one accepted proposal event, one created schedule event, and proposal status `accepted`.
- A fresh request with the **same exact idempotency key** returns the already-created acceptance and schedule identities and preserves counts at one.
- The proxy proves both forwarding threads terminate without leakage.

This closes one controlled acknowledgement-withheld timing after server-side COMMIT completion. It does not establish every network-loss timing, encrypted-protocol interception, or synchronous-replica durability.

### Controlled multi-application-instance exact recovery

A **controlled multi-application-instance exact recovery** corpus extends the ambiguous COMMIT result across **one PostgreSQL primary**.

- The proxy first commits exactly one acceptance lifecycle while withholding `CommandComplete(COMMIT)` from the initiating client.
- Independent direct reads prove the acceptance and draft replacement are already authoritative before recovery workers start.
- **six independent worker processes** each create a distinct 32-character worker-instance identity, private SQLAlchemy pool, session, and live PostgreSQL backend.
- The parent waits until all six workers and six backend PIDs are simultaneously ready behind one release gate.
- The gate opens once; every worker invokes the production source-level guard with the exact same idempotency key.
- All workers return the same acceptance ID and same draft replacement schedule ID, verify the original key, close with `pool_checked_out_after_close=0`, and exit successfully.
- Final authoritative counts remain one acceptance, one replacement, one accepted proposal event, and one created schedule event in `created → accepted` order.

No separate distributed lock service, process-local leader, or fabricated lifecycle row coordinates convergence.

### Controlled physical-standby promotion

A **controlled physical-standby promotion** boundary now exercises two PostgreSQL 16 servers.

- A primary and a separate standby are created with physical streaming replication, separate Docker volumes, `pg_basebackup -Fp -Xs -R`, hot-standby reads, and the same nonempty cluster `system_identifier`.
- Production migrations run on the original primary and replicate to the standby.
- The protocol proxy creates one committed but acknowledgement-withheld acceptance with `synchronous_commit=on`, yielding `database_commit_outcome_unknown`, `retry_safe=false`, and no server retry.
- The test records `pg_current_wal_flush_lsn()` on the primary and waits until the standby **replay-LSN** from `pg_last_wal_replay_lsn()` reaches that exact position.
- Hot-standby reads prove the same acceptance and replacement identities and one event pair before primary loss.
- The original primary is stopped with zero grace, Docker reports it is not running, and a fresh connection to the old endpoint fails.
- The standby is promoted with `pg_promote(true, 60)`, leaves recovery, becomes writable, retains the original system identifier, and advances onto a **new WAL timeline**.
- The application performs **explicit endpoint rotation** to the promoted server and repeats the exact idempotency key through the production guard.
- The promoted primary returns the same acceptance and draft schedule identities. Final counts remain one acceptance, one replacement, one accepted event, and one created event.

This proves one caught-up asynchronous physical standby and manual promotion. It does not prove automatic failover detection, automatic DNS/service-discovery rotation, fencing, split-brain prevention, safe old-primary rewind/rejoin, synchronous-standby durability, multi-instance convergence after promotion, or multi-region failover.

## Database recovery observability

The **database recovery observability** foundation provides **privacy-preserving process metrics** for sanitized HTTP failures and explicit bounded retry behavior.

- Labels are restricted to `database_transaction_retry_required`, `database_commit_outcome_unknown`, `database_pool_timeout`, `database_operation_failed`, and SQLSTATE buckets `40001`, `40P01`, `57014`, `55P03`, `08xxx`, and `unknown`.
- **Exact classification integrity** requires every code to match its transaction-abort, outcome-unknown, pre-transaction, retryable, retry-safe, and invalidated-connection proof flags before counters change.
- **Nonfinite retry timing** is rejected at both policy and registry boundaries: negative, boolean, nonnumeric, `NaN`, and infinite values fail atomically.
- Alert thresholds must be positive integers; booleans and fractional values are rejected.
- Snapshots expose operational errors, transaction aborts, outcome-unknown events, nonretryable errors, invalidated connections, retry observations, scheduled retries, successful convergence, exhausted budgets, outcome-unknown utility exits, and total/maximum delay.
- Snapshot mappings are immutable and counters are protected by a re-entrant lock.
- SQL, parameters, exception messages, idempotency keys, household/user/proposal/schedule IDs, food data, and request payloads are never recorded.
- Alert evaluation emits process-local critical/warning values for outcome unknown, retry exhaustion, transaction-abort volume, invalidated connections, and pool checkout timeout.
- Deterministic OpenMetrics rendering uses bounded labels, rejects malformed values, emits one `# EOF`, and exposes no HTTP endpoint.
- Tests prove sanitization, exact classification partitioning, immutable snapshots, finite-value enforcement, handler/retry integration, deterministic alerts, invalid-input atomicity, and 1,600 concurrent updates.

This is an adapter foundation, not production monitoring. Time windows, persistence, **cross-replica aggregation**, dashboards, paging, deduplication, ownership, runbooks, and SLOs remain.

## PostgreSQL concurrency evidence

Configured PostgreSQL-only coverage includes duplicate/competing acceptance, acceptance versus rejection/invalidation/source execution, plan cancellation and calendar supersession races, repaired approval races, final-task versus schedule completion, repeatable-read support export, lost responses, statement timeout, deadlock, post-commit backend termination, checked-out pool invalidation, repeated serialization retry, controlled single-checkout exhaustion, controlled sustained pool pressure, controlled application-worker recycle, controlled ungraceful worker crash, controlled COMMIT acknowledgement loss, controlled multi-application-instance exact recovery, controlled physical-standby promotion, populated migration rehearsal, and exact migration/dialect assertions with retained JUnit/JSON evidence.

The exact latest hosted executions and artifacts have not been observed in this context. Configured tests are not reported green until inspected.

## Remaining P0/P1 work

- Observe and repair exact current hosted workflows and artifacts.
- Test broader network-loss timings around COMMIT, encrypted transport behavior, operating-system/container/node failure, and synchronous-standby acknowledgement.
- Add automatic failure detection and promotion, DNS/service-discovery or virtual-IP rotation, connection-pool target rotation, fencing, quorum, split-brain prevention, and safe old-primary rewind/rejoin.
- Extend the six-worker application-instance corpus across the promoted-primary boundary; the current physical-promotion corpus performs one explicit recovering request.
- Exercise managed/cloud PostgreSQL behavior, multiple standby selection, regional failure, and multi-region failover.
- Establish representative production capacity under realistic concurrent traffic, queueing, latency, pool sizing, process counts, and duration; the 24-timeout controlled pressure corpus is not representative production capacity.
- Connect process metrics to authenticated production monitoring with cross-replica rates, dashboards, alerts, paging, SLOs, and runbooks.
- Add production-snapshot or production-scale migration rehearsal, backup/restore, and point-in-time recovery.
- Implement authenticated PostgreSQL-backed Playwright, axe, keyboard/reflow/contrast evidence, signed/redacted support packages, retention, and audit linkage.
- Implement execution-aware repair and joint meal/inventory/reservation/shopping/leftover/preparation repair.

## Non-claims

NutriFlavorOS does not establish clinical validity, allergy or medication safety, food safety, contamination state, temperature compliance, actual task performance, human presence, appliance condition, global repair optimality, exhaustive COMMIT-loss recovery, encrypted-transport interception, synchronous-standby durability, operating-system/container/node crash recovery, automatic failover orchestration, automatic endpoint rotation, split-brain fencing, safe old-primary rejoin, multi-application-instance recovery after promotion, managed-database behavior, multi-region failover recovery, representative production capacity, production pool sizing or sustained-load capacity, signed/export-retention guarantees, production monitoring completeness, or current hosted green-build status.
