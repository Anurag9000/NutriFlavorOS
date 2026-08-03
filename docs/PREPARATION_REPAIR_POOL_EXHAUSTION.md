# PostgreSQL Pool Exhaustion Recovery

## Purpose

NutriFlavorOS distinguishes SQLAlchemy connection-pool checkout exhaustion from transaction aborts and ambiguous connection failures.

A `sqlalchemy.exc.TimeoutError` raised by `QueuePool` means the request did not obtain a database connection before `pool_timeout` expired. Therefore no database transaction started in that attempt.

## Public failure contract

The FastAPI database boundary returns HTTP `503` with `Retry-After: 1` and:

- `code=database_pool_timeout`;
- `sqlstate=null`;
- `retryable=true`;
- `retry_safe=true`;
- `transaction_aborted=false`;
- `no_transaction_started=true`;
- `outcome_unknown=false`;
- `failure_stage=connection_checkout`;
- `retry_same_idempotency_key=true`;
- `automatic_retry_performed=false`.

The response never contains the QueuePool exception text, pool internals, SQL, request payload, user data, household identity, or idempotency key.

`retry_safe=true` does not mean the HTTP server retries. It means an explicit client or operator may repeat the exact request because this failed attempt obtained no connection and could not have committed a mutation.

## Explicit bounded retry

`execute_exact_idempotent_database_request` catches both:

- `OperationalError`, classified through SQLSTATE and connection state; and
- SQLAlchemy `TimeoutError`, classified as a connection-checkout timeout.

The utility preserves one normalized idempotency key, applies finite exponential backoff, emits immutable observations, and retries only while `retry_safe=true` and attempts remain.

Pool-timeout observations require:

- `code=database_pool_timeout`;
- `sqlstate=null`;
- `no_transaction_started=true`;
- `retry_safe=true`;
- `outcome_unknown=false`.

If checkout continues to fail through the configured bound, the utility raises `DatabaseRetryExhausted`. It never changes the request key or silently continues forever.

## Real PostgreSQL evidence

The dedicated test creates a separate PostgreSQL SQLAlchemy engine with:

- `QueuePool`;
- `pool_size=1`;
- `max_overflow=0`;
- `pool_timeout=0.1`;
- `pool_pre_ping=true`.

The only pooled connection is checked out and held. Guarded repair-proposal acceptance then attempts its first database access and receives a real QueuePool timeout.

Before releasing the held connection, an independent session requires exactly zero:

- acceptance rows;
- repair-derived replacement schedules;
- proposal `accepted` events;
- replacement schedule `created` events.

The observer then releases the held connection. The second bounded attempt uses the identical idempotency key and creates exactly one immutable acceptance and replacement draft. A later exact retry returns the same acceptance and schedule identities without adding rows or events.

The test must run only on PostgreSQL. SQLite fallback, skip, xfail, fabricated timeout exceptions, and direct raw lifecycle inserts are forbidden.

## Observability

The process-local metrics registry accepts `database_pool_timeout` as one bounded code. It records the event under SQLSTATE bucket `unknown` without storing pool exception text or request/domain identity.

The process alert evaluator exposes a warning threshold for pool checkout timeouts. The deterministic OpenMetrics renderer emits the bounded code series under:

`nutriflavor_database_recovery_classified_events_total{code="database_pool_timeout"}`

No public metrics endpoint is introduced.

## Non-claims

This evidence proves one controlled checkout-timeout and exact recovery scenario. It does not establish:

- production pool sizing;
- sustained concurrency capacity;
- latency or throughput targets;
- fair queueing among requests;
- recovery during process restart or multi-node failover;
- behavior when a connection is lost while COMMIT acknowledgement is in flight;
- cross-replica metrics aggregation;
- current hosted-green status without an observed exact run and artifact.
