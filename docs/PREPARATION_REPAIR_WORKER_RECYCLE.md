# Controlled PostgreSQL Application-Worker Recycle

## Purpose

This boundary verifies recovery when an application worker is deliberately recycled while its own SQLAlchemy connection pool remains fully occupied.

It proves that the **old worker** can report a retry-safe pre-transaction checkout timeout, preserve **exactly zero lifecycle mutation**, close its checked-out PostgreSQL connection during an **orderly recycle**, and allow a **fresh worker process** to recover the exact request with the **same idempotency key**.

This is **not a crash-recovery or multi-node failover proof**. It does not simulate an ungraceful operating-system kill, container eviction, node loss, database-primary loss, DNS change, or COMMIT acknowledgement failure.

## Stable worker identity

Every subprocess creates a cryptographically random 32-character **worker-instance** identity. The pressure report and recycle-completion report must retain the old identity. The fresh recovery process must publish a different worker-instance identity.

Operating-system process IDs and PostgreSQL backend PIDs are still recorded for direct process/database evidence, but correctness does not depend on assuming that an operating-system PID can never be reused.

## Committed starting evidence

The parent PostgreSQL test creates the source calendar, source schedule, immutable repair proposal, and proposal `created` event through production services. Those services commit before the subprocess boundary begins.

A temporary test-only configuration file contains the PostgreSQL URL, household/proposal/actor identities, and exact validated acceptance payload. Configuration and reports remain inside pytest temporary storage and are not uploaded as release artifacts.

## Old-worker pressure phase

The old subprocess creates a separate `QueuePool` with:

- `pool_size=1`;
- `max_overflow=0`;
- `pool_timeout=0.12` seconds;
- `pool_pre_ping=true`.

It checks out the only connection and records its live **PostgreSQL backend PID** with `pg_backend_pid()`. It then invokes production `accept_repair_proposal_with_source_guard` through the bounded exact retry utility with one allowed attempt.

The required result is:

- `code=database_pool_timeout`;
- `retry_safe=true`;
- `no_transaction_started=true`;
- `outcome_unknown=false`;
- `will_retry=false`;
- one checked-out connection still owned by the old worker;
- no schedule or proposal lifecycle mutation.

The old worker writes this bounded report atomically and waits for the parent’s explicit recycle request through stdin.

## Independent pre-recycle proof

While the old worker is still running, the parent PostgreSQL session verifies:

- the reported backend PID is present in `pg_stat_activity`;
- zero repair acceptance rows exist;
- zero replacement schedules exist;
- zero proposal `accepted` events exist;
- zero replacement-schedule `created` events exist.

The timeout is therefore a real checkout failure against a live occupied worker pool, not a fabricated exception or invisible uncommitted fixture.

## Orderly recycle proof

The parent closes the worker’s stdin. The old worker then closes the held connection, proves `pool_checked_out_after_close=0`, disposes its engine, atomically updates its report with `recycle_completed=true`, and exits successfully.

The parent verifies that the old worker-instance identity is unchanged across both reports and polls `pg_stat_activity` until the old PostgreSQL backend disappears. No forceful process signal, `.kill()`, `.terminate()`, skip, xfail, SQLite fallback, or raw lifecycle insertion is used.

## Fresh-worker recovery

The parent starts a **fresh worker process** with a newly constructed engine and the same exact configuration.

The fresh worker must:

- publish a different 32-character worker-instance identity;
- obtain a PostgreSQL backend PID different from the recycled backend;
- invoke the production source-acceptance guard;
- create exactly one acceptance and one draft replacement schedule;
- record schedule version 1 and status `draft`;
- close its session and prove `pool_checked_out_after_close=0`;
- write the acceptance and schedule identities atomically.

The parent independently verifies one acceptance, one replacement schedule, one proposal `accepted` event, one replacement `created` event, and proposal history `created → accepted`.

A final parent-session retry with the **same idempotency key** must return the **same acceptance and schedule identities** rather than create duplicates.

## Verification gate

The dedicated direct-`main` PostgreSQL workflow compiles and executes the recycle helper/test, single and sustained pool-pressure tests, all error/retry/metrics/OpenMetrics/integrity suites, and every related contract. JUnit evidence is retained with the pool-recovery artifact.

Configured execution is not a hosted-green claim until the exact workflow run and artifact are observed.

## Non-claims

This controlled evidence does not establish ungraceful crash recovery, container/pod/VM/host failure recovery, database-primary loss, replica promotion, multi-node failover, cross-replica retry coordination, representative production capacity, safe pool sizing, COMMIT-acknowledgement-in-flight recovery, automatic server-side mutation retry, clinical validity, food safety, actual execution, or deployment readiness.
