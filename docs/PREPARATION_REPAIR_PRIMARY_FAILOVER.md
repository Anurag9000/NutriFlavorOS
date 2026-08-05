# Controlled PostgreSQL Physical-Standby Promotion Recovery

## Purpose

This boundary verifies exact preparation-repair recovery across a real
PostgreSQL primary-to-standby promotion. It extends the controlled COMMIT
acknowledgement-loss and one-primary multi-application-instance evidence with a
second PostgreSQL server created through physical streaming replication.

The evidence uses PostgreSQL 16 containers, production migrations, the
production `accept_repair_proposal_with_source_guard` service, and the existing
test-only PostgreSQL protocol proxy. It does not fabricate acceptance rows,
replacement schedules, lifecycle events, database exceptions, replay positions,
or promotion results.

## Physical cluster construction

The dedicated workflow creates:

- one PostgreSQL primary container;
- one independent PostgreSQL standby container;
- separate persistent Docker volumes;
- one private Docker network;
- physical base-backup initialization through `pg_basebackup -Fp -Xs -R`;
- streaming replication with `wal_level=replica`, WAL senders, retained WAL,
  and hot-standby reads;
- host ports dedicated to the old-primary and standby endpoints.

The setup does not infer streaming from configuration alone. Before migrations
begin, a bounded readiness loop requires both observed runtime states:

- exactly one primary row in `pg_stat_replication` with `state = 'streaming'`;
- standby `pg_stat_wal_receiver.status = 'streaming'`.

The setup additionally requires:

- `pg_is_in_recovery() = false` on the original primary;
- `pg_is_in_recovery() = true` on the standby;
- the same nonempty `system_identifier` from `pg_control_system()` on both
  servers.

A shared system identifier proves that the standby is a physical descendant of
the primary rather than an independently seeded database. The observed sender
and receiver states prove an active physical replication connection before the
reviewed schema and test lifecycle are written.

## Ambiguous committed request before failover

The primary is migrated to reviewed head `20260802_0018`. A complete repair
proposal is created through production services. Acceptance then runs through
the controlled PostgreSQL wire proxy with:

- `SET LOCAL synchronous_commit = on`;
- verification that `SHOW synchronous_commit` returns `on`;
- the complete COMMIT frame forwarded to the primary;
- PostgreSQL `CommandComplete(COMMIT)` observed by the proxy;
- the COMMIT acknowledgement withheld from the application connection.

The application receives an invalidated `OperationalError` classified as:

- `code=database_commit_outcome_unknown`;
- `retryable=true`;
- `retry_safe=false`;
- `outcome_unknown=true`;
- `automatic_retry_performed=false`.

Independent primary reads prove exactly one committed acceptance, one draft
replacement, one proposal `accepted` event, and one replacement `created`
event.

## Replay-position proof

After the committed lifecycle is visible on the primary, the test records
`pg_current_wal_flush_lsn()` as the required recovery position.

The standby remains in recovery while the test polls:

- `pg_last_wal_replay_lsn()`;
- `pg_wal_lsn_diff(replay_lsn, target_lsn) >= 0`.

The primary is not stopped until the standby has replayed at least the exact
recorded flush position. Hot-standby reads then prove the same acceptance and
replacement identities and exactly one matching event pair before promotion.

This is an explicit caught-up asynchronous-replication corpus. It is not a
claim that every asynchronous failover is lossless without checking replay
position.

## Primary loss and promotion

The original primary container is stopped with zero grace time. The test then
requires:

- Docker reports the original primary is not running;
- a fresh connection to the old-primary endpoint fails;
- the standby is promoted with `pg_promote(true, 60)`;
- `pg_is_in_recovery()` becomes false;
- `transaction_read_only` becomes `off`;
- the promoted server retains the original `system_identifier`;
- an autocommit `CHECKPOINT` succeeds;
- the promoted server writes on a different WAL timeline from the old primary.

The changed timeline proves an actual PostgreSQL promotion boundary rather than
only switching between two writable independent databases.

## Explicit endpoint rotation and exact recovery

The application then creates a fresh SQLAlchemy engine against the promoted
server's endpoint. It repeats the exact original proposal ID, payload, actor,
and idempotency key through the production source guard.

The promoted primary must return:

- the same acceptance ID;
- the same replacement schedule ID;
- the original idempotency key;
- draft status and schedule version 1.

Final authoritative counts remain exactly:

- one acceptance;
- one replacement schedule;
- one proposal `accepted` event;
- one replacement `created` event;
- proposal event order `created → accepted`.

The test writes a structured JSON report without database URLs, passwords,
request payloads, or the idempotency key. JUnit and JSON evidence are retained
by the dedicated workflow.

## Deterministic cleanup

An `always()` cleanup step removes both containers, both volumes, and the
private Docker network. Setup also removes stale resources with the exact
run-scoped names before creating the cluster.

The cleanup is infrastructure hygiene, not evidence that an old primary can be
safely rejoined after promotion.

## Non-claims

This controlled physical-standby promotion does **not** establish:

- automatic failover detection or promotion;
- automatic DNS, virtual-IP, proxy, or service-discovery rotation;
- Kubernetes operator, Patroni, repmgr, cloud-database, or managed-service
  behavior;
- synchronous-standby acknowledgement or zero-loss durability without the
  explicit replay-LSN check;
- fencing, STONITH, quorum, split-brain prevention, or lease correctness;
- safe old-primary rewind, rejoin, rebuild, or demotion;
- cascading replicas or multiple standby selection;
- connection-pool rotation without explicit engine replacement;
- retry coordination across multiple application instances after promotion;
- network partitions, partial reachability, or cross-region behavior;
- representative recovery-point objective, recovery-time objective, latency,
  throughput, capacity, or production topology;
- backup/restore or point-in-time recovery;
- clinical, food-safety, actual-execution, or deployment-readiness claims;
- current hosted green status without the exact workflow run and artifacts.

The evidence proves one controlled PostgreSQL 16 physical standby that is
caught up to a recorded WAL position, promoted after the original primary is
stopped, and used through an explicit new endpoint to recover one exact
idempotent preparation-repair acceptance without duplication.
