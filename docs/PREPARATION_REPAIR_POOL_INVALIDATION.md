# Preparation Repair PostgreSQL Pool Invalidation Recovery

## Purpose

This boundary verifies recovery when an application session already holds a PostgreSQL connection that becomes dead before a state-changing repair acceptance begins.

It is distinct from:

- transaction aborts such as serialization failure, deadlock, statement timeout, or lock timeout;
- post-commit connection loss, where the mutation committed before the connection failed;
- primary failover or multi-node topology changes;
- connection loss while the COMMIT acknowledgement itself is in flight.

## Engine prerequisite

The application engine uses `pool_pre_ping=True`. Pre-ping protects connections when they are checked out from the pool. It cannot prevent a connection that is already checked out from dying after checkout, so the service must surface the first failed operation and allow SQLAlchemy to invalidate that connection.

## Real PostgreSQL probe

The test `test_postgres_invalidated_checked_out_connection_recovers_on_fresh_session` performs this sequence:

1. create a current repair proposal and exact acceptance payload;
2. open a worker session and execute `SELECT pg_backend_pid()` so it holds a real checked-out PostgreSQL connection;
3. use an independent administrator session to execute `SELECT pg_terminate_backend(:pid)` against that worker;
4. invoke guarded acceptance on the dead checked-out connection;
5. require a real SQLAlchemy `OperationalError` with `connection_invalidated=true`;
6. classify the failure as `database_commit_outcome_unknown`, `outcome_unknown=true`, `retryable=true`, `retry_safe=false`, and `automatic_retry_performed=false`;
7. independently prove that no acceptance, replacement schedule, accepted proposal event, or replacement-created event exists and that the proposal is still `proposed` at the same version;
8. open a fresh session and require its backend PID to differ from the terminated PID;
9. execute the exact same acceptance payload and idempotency key successfully;
10. repeat the exact request from another fresh session and require the original acceptance and replacement identities;
11. require exactly one acceptance, one replacement schedule, one proposal `accepted` event, one replacement `created` event, and `created → accepted` proposal history.

## Retry semantics

The error is `retryable` because the prescribed client action is to issue the exact request again with the same idempotency key. It is not `retry_safe` because a connection failure alone cannot prove whether an arbitrary transaction committed. In this specific test, independent evidence proves the failure occurred before any acceptance mutation, but the public classifier remains conservative and consistent for all invalidated connections.

The server performs no automatic retry and does not transparently replay a state-changing operation on a replacement connection.

## Scope and non-claims

This proves one checked-out dead connection is invalidated and a fresh pooled connection can recover exact idempotent acceptance. It does not establish:

- pool behavior under sustained concurrency or exhaustion;
- connection recycling, max-overflow, timeout, or lifetime tuning;
- primary failover, DNS/service discovery changes, or replica promotion;
- transaction replay across process restarts;
- COMMIT-acknowledgement-in-flight outcome recovery;
- hosted green status until the exact workflow run and JUnit artifact are observed.
