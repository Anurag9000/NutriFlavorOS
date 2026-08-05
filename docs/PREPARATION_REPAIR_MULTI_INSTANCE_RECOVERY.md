# Controlled Multi-Application-Instance Exact Recovery

## Purpose

This boundary proves that several independent NutriFlavorOS application worker processes can recover the same ambiguous repair-acceptance request through the authoritative PostgreSQL idempotency record.

It is deliberately a **single-primary PostgreSQL** proof. “Application instance” means a separate operating-system process with its own worker-instance identity, SQLAlchemy engine, connection pool, session, and live PostgreSQL backend. It does not mean a PostgreSQL read replica or promoted database primary.

## Triggering the ambiguous outcome

The test first uses the controlled PostgreSQL COMMIT-acknowledgement-loss proxy:

1. production guarded repair acceptance runs with `synchronous_commit=on`;
2. the complete COMMIT frame is forwarded to PostgreSQL;
3. PostgreSQL emits `CommandComplete(COMMIT)`;
4. the proxy withholds that acknowledgement and closes the connection;
5. the client receives `database_commit_outcome_unknown`, `retry_safe=false`, and `automatic_retry_performed=false`;
6. an independent direct read proves exactly one acceptance, one draft replacement, one accepted proposal event, and one created schedule event are committed.

No application worker automatically retries that ambiguous failure.

## Six coordinated recovery workers

After the authoritative committed state is visible, the test launches **six independent application worker processes**.

Each worker:

- creates its own `QueuePool(pool_size=1, max_overflow=0, pool_pre_ping=true)`;
- creates a distinct 32-character worker-instance identity;
- opens a distinct live PostgreSQL backend;
- publishes a ready report without the idempotency key or request payload;
- waits behind the same parent-controlled release gate;
- invokes `accept_repair_proposal_with_source_guard` with the exact original request and idempotency key;
- closes its session and returns to `pool_checked_out_after_close=0`.

The parent opens the gate only after all six worker processes and six PostgreSQL backends are simultaneously ready.

## Required convergence

Every worker must return:

- the same existing acceptance ID;
- the same existing draft replacement schedule ID;
- schedule version `1` and status `draft`;
- proof that the returned acceptance carries the exact original idempotency key;
- zero checked-out connections after its session closes.

After all workers exit, authoritative committed state must still contain exactly:

- one acceptance;
- one replacement schedule;
- one accepted proposal event;
- one created schedule event;
- proposal event order `created → accepted`.

No worker may create a second lifecycle or reinterpret the ambiguous result as an uncommitted mutation.

## Authority

The coordination authority is the existing PostgreSQL transaction and uniqueness model plus the production source-level acceptance guard. No separate distributed lock service, in-memory leader, browser state, process-local cache, or fabricated lifecycle row participates.

## Process hygiene

The test uses bounded waits and a `finally` cleanup path. Any worker still alive after a failed assertion is killed and reaped. Successful workers must close their sessions, return their pools to zero checked-out connections, and dispose their engines.

## Non-claims

This controlled proof does not establish:

- PostgreSQL read-replica or primary-promotion behavior;
- multi-node PostgreSQL failover;
- DNS, service-discovery, load-balancer, or connection-string rotation;
- encrypted COMMIT interception;
- cross-region latency or partition handling;
- representative production concurrency, fairness, throughput, or capacity;
- a generic distributed transaction protocol;
- exactly-once execution outside the reviewed repair-acceptance lifecycle;
- hosted green status without observing the exact current workflow and artifact.
