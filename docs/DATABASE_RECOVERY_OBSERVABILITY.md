# Database Recovery Observability

## Purpose

NutriFlavorOS records privacy-preserving process metrics for operational database failures, connection-pool checkout timeouts, and explicit bounded retry behavior.

The observability core **never receives or stores SQL text**, SQL parameters, exception messages, idempotency keys, household IDs, user IDs, proposal IDs, schedule IDs, food data, or request payloads.

It exposes **no unauthenticated HTTP metrics endpoint**. Deployments may adapt the in-process snapshot or sanitized OpenMetrics rendering to their authenticated monitoring stack.

## Metric sources

### HTTP database-failure boundary

Handled SQLAlchemy `OperationalError` values record one bounded code, one bounded SQLSTATE bucket, transaction-abort/outcome-unknown/retry flags, and whether SQLAlchemy invalidated the connection.

Handled SQLAlchemy `TimeoutError` values use bounded code `database_pool_timeout`, SQLSTATE bucket `unknown`, `no_transaction_started=true`, `retry_safe=true`, and `outcome_unknown=false`. The handler records no exception message or pool internals.

Every public response remains sanitized and reports `automatic_retry_performed=false`.

### Explicit bounded retry utility

Every failed bounded-retry attempt records bounded code/SQLSTATE, `retry_safe`, `outcome_unknown`, `no_transaction_started`, whether another attempt was scheduled, and the selected delay. Separate counters record successful convergence, exhaustion, and ambiguous utility exits.

The registry never receives the idempotency key carried by `DatabaseRetryObservation`.

## Exact snapshot fields

`DatabaseRecoveryMetricsSnapshot` is immutable and contains exactly:

- `generated_at`;
- `operational_error_total`;
- `transaction_abort_total`;
- `outcome_unknown_total`;
- `nonretryable_error_total`;
- `retry_observation_total`;
- `retry_scheduled_total`;
- `retry_success_after_retry_total`;
- `retry_exhausted_total`;
- `utility_outcome_unknown_total`;
- `invalidated_connection_total`;
- `retry_delay_seconds_total`;
- `retry_delay_seconds_max`;
- immutable `code_counts`;
- immutable `sqlstate_counts`.

Pool checkout timeouts are represented through bounded `code_counts["database_pool_timeout"]`; no tenant-specific or pool-instance label is introduced.

Counters are monotonic until process restart. `reset_for_tests()` exists only for deterministic tests and must not be called by production code.

## Exact classification and numeric integrity

Every recorded event must use one reviewed code/proof partition:

- transaction-abort proof maps to `database_transaction_retry_required`;
- outcome ambiguity maps to `database_commit_outcome_unknown`;
- pre-transaction checkout proof maps to `database_pool_timeout`;
- absence of retry proof maps to `database_operation_failed`.

The code and proof flags must agree. `retryable`, `retry_safe`, `transaction_aborted`, `outcome_unknown`, `no_transaction_started`, and connection invalidation are cross-validated before any counter changes.

Retry delays must be finite and nonnegative. Boolean, nonnumeric, negative, `NaN`, and infinite values are rejected. Alert policies require positive integer thresholds; booleans and fractional thresholds are rejected. Every invalid classification, delay, or threshold fails atomically without changing counters, labels, totals, or delay aggregates.

## Sanitized OpenMetrics adapter

`render_database_recovery_openmetrics` converts one immutable snapshot into deterministic OpenMetrics text using prefix `nutriflavor_database_recovery`.

The renderer provides:

- HELP and TYPE declarations for every scalar counter and delay gauge;
- sorted `code` series restricted to four reviewed error codes: `database_transaction_retry_required`, `database_commit_outcome_unknown`, `database_pool_timeout`, and `database_operation_failed`;
- sorted `sqlstate` series restricted to `40001`, `40P01`, `57014`, `55P03`, `08xxx`, and `unknown`;
- deterministic output ending in one `# EOF` marker;
- no timestamp, request, tenant, household, user, proposal, schedule, food, or idempotency label;
- no HTTP route or authentication decision.

It rejects **unreviewed code or SQLSTATE labels**, negative or noninteger counters, negative/nonfinite delays, and malformed labeled-series counts.

The renderer is an in-process adapter only. A deployment must choose an authenticated/private publishing mechanism and must not add unbounded labels.

## Alerts

`DatabaseRecoveryAlertPolicy` defines positive integer process-local thresholds for:

- **outcome-unknown events: critical**;
- exhausted retry budgets: warning;
- transaction-abort volume: warning;
- invalidated checked-out connections: warning;
- connection-pool checkout timeout: warning.

`evaluate_database_recovery_alerts` returns immutable sanitized alert values. These are adapter inputs, not a complete production alerting system. Deployments still need time windows, rates, **cross-replica aggregation**, persistence, dashboards, paging, deduplication, ownership, runbooks, and SLOs.

## Thread safety and failure behavior

The registry uses a re-entrant lock. Concurrent updates are monotonic, and snapshots copy counters into immutable mappings.

Invalid metric combinations fail before counters change. Outcome-unknown observations cannot schedule automatic retries, pre-transaction proof is reserved for pool checkout timeout, and invalidated connections must remain outcome-unknown.

## Controlled sustained pressure aggregation

The controlled sustained PostgreSQL pool-pressure test occupies a two-connection pool and executes three synchronized waves with eight callers per wave.

All **24 checkout timeouts** are recorded through the explicit bounded retry utility as 24 `database_pool_timeout` code-count events, 24 retry observations, 24 exhausted single-attempt budgets, zero scheduled retries, zero outcome-unknown events, zero invalidated connections, and zero HTTP operational-error events.

The test also proves zero lifecycle mutation during pressure and `checkedout() == 0` after capacity is released and exact-key recovery completes. These counts are deterministic evidence for the controlled corpus, not representative production rates or capacity.

## Verification

Focused tests prove:

- unknown codes and SQLSTATEs collapse to bounded safe buckets;
- every reviewed code remains recordable with its exact proof flags;
- mismatched code/proof combinations fail before any counter changes;
- connection SQLSTATEs collapse to `08xxx`;
- SQL, parameters, exception messages, idempotency keys, and domain IDs do not appear in snapshots or OpenMetrics text;
- snapshots are immutable;
- nonfinite timing values and noninteger alert thresholds fail atomically;
- HTTP errors and bounded retries update exact counters;
- pool checkout timeout produces one bounded alert and OpenMetrics series;
- the three-wave pressure corpus produces exactly 24 checkout-timeout observations and exhausted single-attempt budgets;
- alert thresholds produce deterministic severity and counts;
- **1,600 concurrent updates** remain exact;
- OpenMetrics ordering and output are deterministic;
- unbounded labels and malformed values fail closed.

## Non-claims

This implementation does not provide a public or authenticated metrics HTTP endpoint, persistent counters across process restarts, cross-replica aggregation, time-windowed rates or histograms, production dashboards/paging/incident automation, representative production capacity, production pool sizing, automatic mutation retries, or proof of hosted green workflows without observed exact runs and artifacts.
