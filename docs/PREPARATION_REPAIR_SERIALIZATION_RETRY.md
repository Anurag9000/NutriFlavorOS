# Preparation Repair Bounded Exact Serialization Retry

## Purpose

This boundary provides a finite, observable client/operator retry utility for one exact idempotent request after PostgreSQL proves that a transaction aborted.

It is not imported by FastAPI mutation handlers and does not add hidden server-side mutation retries.

## Retry-safety partition

The database error classifier separates two concepts:

- `retryable=true` means the prescribed caller action is to repeat the exact request with the same idempotency key;
- `retry_safe=true` means PostgreSQL proved that the transaction aborted, so a bounded automatic client retry is permitted;
- `outcome_unknown=true` means a connection failure may have occurred around commit and the utility must not replay automatically.

Transaction-abort SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` are retry-safe. Connection exceptions and invalidated connections remain outcome-unknown and use `DatabaseOutcomeUnknown` rather than automatic replay.

## Bounded policy

`ExactDatabaseRetryPolicy` declares:

- `max_attempts`, constrained to 1–20;
- `base_delay_seconds`;
- `max_delay_seconds`;
- finite exponential backoff capped by the configured maximum.

`execute_exact_idempotent_database_request`:

1. requires an already-normalized, nonblank idempotency key;
2. passes the unchanged key and one-based attempt number to the caller-supplied operation;
3. catches only SQLAlchemy `OperationalError`;
4. classifies the failure through the application database-error boundary;
5. emits one immutable `DatabaseRetryObservation` for every failed attempt;
6. sleeps only before another retry-safe attempt;
7. raises `DatabaseRetryExhausted` at the exact bound;
8. raises `DatabaseOutcomeUnknown` immediately for ambiguous connections;
9. re-raises nonretryable failures without sleeping or replaying.

The utility does not own a database session, issue a commit, choose a mutation endpoint, or create a new idempotency key.

## Real PostgreSQL repeated-serialization proof

The test `test_postgres_repeated_serialization_failures_retry_exact_request_once` uses genuine `SERIALIZABLE` transactions.

For each of the first three attempts:

1. a worker reads the household version, establishing its serializable snapshot;
2. an independent transaction advances that exact household row and commits;
3. guarded proposal acceptance then attempts to lock/use the stale snapshot;
4. PostgreSQL aborts the worker with SQLSTATE `40001`;
5. the worker session closes and the observation records `retry_safe=true`, `outcome_unknown=false`, and `will_retry=true`.

The fourth exact-key attempt receives no conflicting update and commits exactly one acceptance and one replacement draft. A fresh direct retry with the same idempotency key returns the original identities.

Final evidence requires:

- exactly four operation attempts;
- exactly three consecutive `40001` observations;
- the same idempotency key on every attempt;
- exactly one acceptance row;
- exactly one replacement schedule;
- exactly one proposal `accepted` event;
- exactly one replacement `created` event;
- proposal history `created → accepted`.

## Observability

Every failed attempt exposes:

- attempt number and maximum attempts;
- unchanged idempotency key;
- structured code and SQLSTATE;
- `retryable`, `retry_safe`, and `outcome_unknown` flags;
- whether another attempt will occur;
- selected delay.

The caller supplies the observer and sleep function, allowing metrics, logs, tracing, tests, or command-line reporting without embedding infrastructure into domain services.

## Non-claims

This proves bounded exact retry for repeated serialization aborts and unit-level behavior for timeout/deadlock classifications. It does not establish:

- server-side automatic retry;
- automatic replay after an outcome-unknown connection failure;
- multi-process coordination of client retry budgets;
- production retry-rate tuning or latency SLOs;
- primary failover or COMMIT-acknowledgement-in-flight recovery;
- hosted green status until the exact workflow run and retained JUnit evidence are observed.

`automatic_retry_performed=false` remains the HTTP server contract. The bounded utility is an explicit caller decision around one exact idempotent request.
