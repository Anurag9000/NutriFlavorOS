# Preparation Repair Bounded Exact Serialization Retry

## Purpose

This **Bounded Exact Serialization Retry** boundary provides a finite, observable client/operator utility for one exact idempotent request after either:

- PostgreSQL proves that a transaction aborted; or
- SQLAlchemy proves that pool checkout failed before any connection or transaction was acquired.

It is not imported by FastAPI mutation handlers and does not add hidden server-side mutation retries.

## Retry-safety partition

The database error classifier separates caller action from proof strength:

- `retryable=true` means the prescribed caller action is to repeat the exact request with the **same idempotency key**;
- `retry_safe=true` means either PostgreSQL proved the transaction aborted or checkout failed before a transaction started;
- `no_transaction_started=true` is reserved for `database_pool_timeout`;
- `outcome_unknown=true` means a connection failure may have occurred around commit and the utility must not replay automatically.

Transaction-abort SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` are retry-safe. Pool checkout timeout is retry-safe without claiming a transaction abort. Connection exceptions and invalidated connections remain outcome-unknown and use `DatabaseOutcomeUnknown` rather than automatic replay.

## Bounded policy

`ExactDatabaseRetryPolicy` declares:

- `max_attempts`, which must be a **positive integer** from 1 through 20;
- `base_delay_seconds`, which must be finite and nonnegative;
- `max_delay_seconds`, which must be finite and nonnegative and no smaller than the base delay;
- finite exponential backoff capped by the configured maximum.

Boolean, nonnumeric, negative, `NaN`, positive infinity, and negative infinity timing values are rejected before the operation runs. Attempt numbers supplied to `delay_for_failed_attempt` must also be positive integers.

`execute_exact_idempotent_database_request`:

1. requires an already-normalized, nonblank idempotency key;
2. passes the unchanged key and one-based attempt number to the caller-supplied operation;
3. catches only SQLAlchemy `OperationalError` and SQLAlchemy `TimeoutError`;
4. classifies both through the application database-error boundary;
5. emits one immutable `DatabaseRetryObservation` for every failed attempt;
6. records whether the failure is transaction-aborted, outcome-unknown, or pre-transaction checkout exhaustion;
7. sleeps only before another retry-safe attempt;
8. raises `DatabaseRetryExhausted` at the exact bound;
9. raises `DatabaseOutcomeUnknown` immediately for ambiguous connections;
10. re-raises nonretryable failures without sleeping or replaying.

The utility does not own a database session, issue a commit, choose a mutation endpoint, or create a new idempotency key.

## Exact classification and numeric integrity

Every observation must use one reviewed classification:

- `database_transaction_retry_required` with retry-safe transaction-abort proof;
- `database_pool_timeout` with `no_transaction_started=true`;
- `database_commit_outcome_unknown` with `retry_safe=false` and no automatic replay;
- `database_operation_failed` with no retry proof.

Code and proof flags must agree before any metric counter changes. Retry delays must be finite and nonnegative. Process alert thresholds must be positive integers. Invalid combinations, malformed delays, or malformed thresholds fail atomically and produce no partial observations or counters.

## Real PostgreSQL repeated-serialization proof

The test `test_postgres_repeated_serialization_failures_retry_exact_request_once` uses genuine `SERIALIZABLE` transactions.

For each of the first three attempts:

1. a worker reads the household version, establishing its serializable snapshot;
2. an independent transaction advances that exact household row and commits;
3. guarded proposal acceptance attempts to lock/use the stale snapshot;
4. PostgreSQL aborts the worker with SQLSTATE `40001`;
5. the worker session closes and the observation records `retry_safe=true`, `outcome_unknown=false`, and `will_retry=true`.

The fourth exact-key attempt receives no conflicting update and commits exactly one acceptance and one replacement draft. A fresh direct retry with the same idempotency key returns the original identities.

Final evidence requires exactly four operation attempts, exactly three consecutive `40001` observations, one unchanged idempotency key, one acceptance, one replacement schedule, one proposal `accepted` event, one replacement `created` event, and proposal history `created → accepted`.

## Controlled pool-checkout evidence

The same utility is exercised against real `QueuePool` exhaustion:

- the single-checkout probe retries after one held connection is released;
- the controlled sustained pressure corpus records 24 pre-transaction checkout timeouts across three synchronized waves;
- every pressure failure uses `database_pool_timeout`, `retry_safe=true`, `no_transaction_started=true`, and `outcome_unknown=false`;
- capacity recovery uses the identical request key and produces one immutable accepted replacement.

These controlled tests do not establish representative production capacity or production pool sizing.

## Observability

Every failed attempt exposes attempt number, maximum attempts, unchanged idempotency key, structured code/SQLSTATE, proof flags, retry decision, and finite selected delay. The metrics registry receives only bounded classifications and aggregate timing values; it never receives the idempotency key or domain identifiers.

## Non-claims

This evidence does not establish server-side automatic retry, automatic replay after an outcome-unknown connection failure, multi-process coordination of retry budgets, representative production retry-rate tuning, primary failover, COMMIT-acknowledgement-in-flight recovery, or hosted green status without the exact observed workflow and retained artifact.

`automatic_retry_performed=false` remains the HTTP server contract. The bounded utility is an explicit caller decision around one exact idempotent request.
