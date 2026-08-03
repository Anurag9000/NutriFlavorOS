# Controlled Sustained PostgreSQL Pool Pressure

## Purpose

This evidence extends the single-checkout pool-exhaustion probe into a deterministic, repeated concurrency boundary. It demonstrates that repeated SQLAlchemy QueuePool checkout failures remain pre-transaction, produce exactly zero lifecycle mutation, preserve one exact idempotency key, and recover without leaked checkouts after capacity returns.

It is **not representative production capacity** and does not establish throughput, latency, sizing, autoscaling, or deployment readiness.

## Controlled configuration

The PostgreSQL-only test constructs a separate constrained engine with:

- `QueuePool`;
- `pool_size=2`;
- `max_overflow=0`;
- `pool_timeout=0.12` seconds;
- `pool_pre_ping=true`.

Both connections are checked out and held with a live `SELECT 1`. While the pool is fully occupied, the test executes **three synchronized waves**, with **eight callers per wave**. Every caller attempts the same guarded repair-proposal acceptance through the bounded exact retry utility with `max_attempts=1`.

The total pressure corpus is therefore **24 checkout timeouts**.

## Required timeout classification

Every failed checkout must report:

- `code=database_pool_timeout`;
- `retryable=true`;
- `retry_safe=true`;
- `transaction_aborted=false`;
- `no_transaction_started=true`;
- `outcome_unknown=false`;
- `will_retry=false` for the single-attempt probe;
- `automatic_retry_performed=false` at the server boundary.

Pool checkout timeout is retry-safe only because no database connection or transaction was acquired. This rule does not apply to connection failures after a transaction may have committed.

## Zero-mutation evidence

After each of the three waves, an independent PostgreSQL session verifies exactly zero lifecycle mutation for the target proposal:

- zero repair acceptance rows;
- zero replacement schedules;
- zero proposal `accepted` events;
- zero replacement-schedule `created` events.

The test does not fabricate timeout exceptions, write lifecycle rows directly, use SQLite, skip, xfail, or weaken database constraints.

## Metrics evidence

After the pressure waves, the process-local registry must contain:

- `database_pool_timeout=24` in bounded code counts;
- 24 retry observations;
- 24 exhausted single-attempt budgets;
- zero scheduled retries;
- zero outcome-unknown events;
- zero invalidated connections;
- zero HTTP operational-error events, because this evidence exercises the explicit caller utility directly.

No SQL text, parameters, exception messages, idempotency keys, household IDs, user IDs, proposal IDs, schedule IDs, food data, or request payloads may enter metrics or OpenMetrics labels.

## Exact recovery

After all held connections are released:

1. `checkedout() == 0` must hold before recovery.
2. The exact request is repeated with the **same idempotency key**.
3. Exactly one acceptance and one replacement draft are created.
4. Exactly one proposal `accepted` event and one replacement `created` event exist.
5. A later exact retry returns the same acceptance and schedule identities.
6. A fresh `SELECT 1` succeeds.
7. `checkedout() == 0` holds again after recovery.

## Verification gate

The direct-`main` workflow compiles and executes:

- the single occupied-pool checkout test;
- the controlled sustained pressure test;
- pool-timeout HTTP/retry/metrics unit tests;
- the single-exhaustion contract;
- the sustained-pressure contract;
- the synchronized release identity validator.

The workflow retains JUnit evidence. Configuration alone is not a hosted-green claim; the exact run and artifact must be observed before reporting success.

## Non-claims

This controlled corpus does not prove:

- representative production capacity;
- sustained real-traffic throughput or tail latency;
- fairness among waiting callers;
- safe pool sizing for any deployment;
- multi-process or cross-replica aggregation;
- primary failover or DNS/service-discovery recovery;
- connection loss while COMMIT acknowledgement is in flight;
- indefinite pressure handling;
- clinical, food-safety, actual-execution, or deployment readiness.
