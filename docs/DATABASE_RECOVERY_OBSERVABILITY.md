# Database Recovery Observability

## Purpose

NutriFlavorOS records privacy-preserving process metrics for operational database failures and explicit bounded retry behavior.

The observability core **never receives or stores SQL text**, SQL parameters, exception messages, idempotency keys, household IDs, user IDs, proposal IDs, schedule IDs, food data, or request payloads.

It exposes **no unauthenticated HTTP metrics endpoint**. Deployments may adapt the in-process snapshot to their authenticated monitoring stack.

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

Every failed bounded-retry attempt records bounded code/SQLSTATE, `retry_safe`, `outcome_unknown`, whether another attempt was scheduled, and the selected delay.

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

Counters are monotonic until process restart. `reset_for_tests()` exists only for deterministic tests and must not be called by production code.

## Alerts

`DatabaseRecoveryAlertPolicy` defines positive process-local thresholds for:

- **outcome-unknown events: critical**;
- exhausted retry budgets: warning;
- transaction-abort volume: warning;
- invalidated checked-out connections: warning.

`evaluate_database_recovery_alerts` returns immutable alert values containing code, severity, observed count, threshold, and a sanitized message.

These are adapter inputs, not a complete production alerting system. Deployments still need time windows, rates, **cross-replica aggregation**, persistence, dashboards, paging, deduplication, ownership, runbooks, and SLOs.

## Thread safety and failure behavior

The registry uses a re-entrant lock. Concurrent updates are monotonic, and snapshots copy counters into immutable mappings.

Invalid combinations fail before counters change:

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
- **1,600 concurrent updates** remain exact;
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
