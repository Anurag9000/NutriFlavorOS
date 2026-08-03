# Database Recovery Observability

## Purpose

NutriFlavorOS records privacy-preserving process metrics for operational database failures and explicit bounded retry behavior.

The observability core never receives or stores SQL text, SQL parameters, exception messages, idempotency keys, household IDs, user IDs, proposal IDs, schedule IDs, food data, or request payloads.

It exposes no unauthenticated HTTP metrics endpoint. Deployments may adapt the in-process snapshot to their authenticated monitoring stack.

## Metric sources

### HTTP operational-error boundary

Every handled SQLAlchemy `OperationalError` records only:

- one bounded code: `database_transaction_retry_required`, `database_commit_outcome_unknown`, or `database_operation_failed`;
- one bounded SQLSTATE bucket: `40001`, `40P01`, `57014`, `55P03`, `08xxx`, or `unknown`;
- `transaction_aborted`;
- `outcome_unknown`;
- `retryable`;
- `retry_safe`;
- whether SQLAlchemy marked the connection invalidated.

The public error response remains sanitized and reports `automatic_retry_performed=false`.

### Explicit bounded retry utility

Every failed bounded-retry attempt records:

- bounded code and SQLSTATE bucket;
- `retry_safe` and `outcome_unknown`;
- whether another attempt was scheduled;
- the selected delay.

Separate counters record:

- retries scheduled;
- successful convergence after at least one retry;
- exhausted retry budgets;
- utility outcomes that remained unknown and were not replayed.

The registry never receives the idempotency key carried by `DatabaseRetryObservation`.

## Snapshot

`DatabaseRecoveryMetricsSnapshot` is immutable and contains:

- operational-error totals;
- transaction-abort, outcome-unknown, nonretryable, and invalidated-connection totals;
- retry observation, scheduled retry, successful-after-retry, exhaustion, and utility-outcome-unknown totals;
- total and maximum selected retry delay;
- immutable bounded code and SQLSTATE-count mappings;
- UTC generation time.

Counters are monotonic until process restart. `reset_for_tests()` exists only for deterministic tests and must not be called by production code.

## Alerts

`DatabaseRecoveryAlertPolicy` defines positive process-local thresholds for:

- outcome-unknown events: critical;
- exhausted retry budgets: warning;
- transaction-abort volume: warning;
- invalidated checked-out connections: warning.

`evaluate_database_recovery_alerts` returns immutable alert values containing code, severity, observed count, threshold, and a sanitized message.

These are adapter inputs, not a complete production alerting system. Deployments still need time windows, rates, aggregation across replicas, persistence, dashboards, paging, deduplication, ownership, runbooks, and SLOs.

## Thread safety and failure behavior

The process registry uses a re-entrant lock. Concurrent updates are monotonic, and snapshots copy counters into immutable mappings.

Invalid metric combinations fail before counters change:

- `retry_safe=true` requires a proven transaction abort;
- `outcome_unknown=true` cannot be retry-safe;
- `will_retry=true` requires retry-safe evidence;
- outcome-unknown observations cannot schedule an automatic retry;
- retry delay cannot be negative.

## Verification

Focused tests prove:

- unknown codes and SQLSTATEs collapse to bounded safe buckets;
- connection SQLSTATEs collapse to `08xxx`;
- SQL, parameters, exception messages, and idempotency keys do not appear in snapshots;
- snapshots are immutable;
- HTTP errors update sanitized counters;
- bounded retries record scheduled attempts and successful convergence;
- exhaustion and outcome-unknown utility paths are distinct;
- alert thresholds produce deterministic severity and counts;
- 1,600 concurrent updates remain exact;
- invalid combinations leave counters unchanged.

## Non-claims

This implementation does not provide:

- a public or authenticated metrics HTTP endpoint;
- persistent counters across process restarts;
- cross-replica aggregation;
- time-windowed rates or histograms;
- production dashboards, paging, or incident automation;
- automatic mutation retries;
- proof of hosted green workflows without observed exact runs and artifacts.
