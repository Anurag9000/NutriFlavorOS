# PostgreSQL Ungraceful Application-Worker Crash Recovery

## Purpose

This boundary proves exact preparation-repair recovery after a real application
worker is terminated with `SIGKILL`. It covers two controlled PostgreSQL cases:

1. the worker dies while holding the only checked-out pool connection after a
   separate exact request has timed out before transaction start;
2. the worker dies after the production acceptance service has flushed its
   complete lifecycle mutation inside an open transaction but before commit.

Both cases use the production
`accept_repair_proposal_with_source_guard` service and the same exact
idempotency key during recovery. No lifecycle row is fabricated.

## Stable identities

Every subprocess publishes:

- a random 32-character worker-instance identity;
- its operating-system process ID as a diagnostic observation;
- its live PostgreSQL backend PID;
- the proposal and exact request supplied through a temporary JSON document.

The fresh recovery worker must have a different worker-instance identity and a
different PostgreSQL backend PID from the crashed worker. The operating-system
PID is not used as a uniqueness proof because **OS PID reuse** is legal after a
process exits.

## Checkout-holder crash

The old worker creates a PostgreSQL `QueuePool` with:

- `pool_size=1`;
- `max_overflow=0`;
- `pool_timeout=0.12`;
- `pool_pre_ping=true`.

It checks out the only connection, records its backend PID, and attempts the
exact guarded acceptance through the bounded retry utility with one permitted
attempt. The request receives `database_pool_timeout` with:

- `retry_safe=true`;
- `no_transaction_started=true`;
- `outcome_unknown=false`;
- no scheduled retry;
- exactly zero lifecycle mutation.

The parent confirms the backend is live and committed reads still show a
`proposed` proposal with zero acceptance, replacement schedule, accepted event,
and replacement-created event. It then sends real `SIGKILL`—not an orderly
stdin close, `SIGTERM`, fabricated exception, or mocked crash.

After PostgreSQL removes the dead backend, committed state remains unchanged.
A fresh worker repeats the same exact request and creates one accepted
replacement. A later retry returns the same acceptance and schedule identities.

## Flushed-open-transaction crash

A custom test-only SQLAlchemy `Session` overrides only `commit()`:

1. it calls `flush()` so the production service has inserted the acceptance,
   replacement schedule, accepted proposal event, and created schedule event;
2. it records the live PostgreSQL backend PID and transaction-local counts;
3. it deliberately does **not** call the real commit;
4. it waits for the parent to send `SIGKILL`.

Inside the child transaction, all four lifecycle counts are exactly one and the
proposal status is `accepted`. At the same moment, an independent committed
reader still sees the proposal as `proposed` and every lifecycle count as zero.

After `SIGKILL`, the parent waits until the old PostgreSQL backend disappears.
PostgreSQL rollback leaves exactly zero committed lifecycle mutation. A fresh
worker then repeats the identical idempotent acceptance, creates exactly one
replacement, and a subsequent exact retry returns the same identities.

## Deterministic process cleanup

The parent owns cleanup through a `finally` boundary. `_kill_worker()` performs
only the real `SIGKILL` delivery and exit-code assertion. The final cleanup
function guarantees the subprocess is stopped and consumes stdout/stderr
exactly once, avoiding reads from already-closed pipes while preserving failure
diagnostics.

## Evidence requirements

The PostgreSQL tests require:

- real subprocesses;
- real `signal.SIGKILL` delivery;
- exact old-worker and old-backend liveness before termination;
- old-backend absence after termination;
- transaction-local flushed counts of one versus independently visible counts
  of zero;
- zero committed mutation after each crash;
- a different recovery worker-instance identity and PostgreSQL backend PID;
- tolerance for legal OS PID reuse;
- one final acceptance, one replacement schedule, one accepted proposal event,
  and one created schedule event;
- final proposal event order `created → accepted`;
- exact same-key idempotent replay;
- exactly one subprocess-output collection during final cleanup.

The focused PostgreSQL workflow retains JUnit evidence and runs static contracts
that reject skip, xfail, SQLite fallback, mocked failure, raw lifecycle inserts,
or graceful-shutdown substitution.

## Non-claims

This controlled crash boundary does not prove:

- loss while PostgreSQL commit acknowledgement itself is in flight;
- operating-system, container-runtime, Kubernetes, or node failure behavior;
- multiple application replicas or cross-replica retry coordination;
- PostgreSQL primary loss, replica promotion, DNS/service-discovery changes, or
  multi-node failover;
- representative production traffic, latency, capacity, or indefinite pressure;
- hosted workflow success without inspection of exact current runs and artifacts.
