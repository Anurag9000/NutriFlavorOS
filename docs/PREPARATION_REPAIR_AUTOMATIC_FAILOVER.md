# Controlled Automatic PostgreSQL Failover and Stable-Endpoint Recovery

## Purpose

This boundary extends the controlled physical-standby promotion corpus with
failure-triggered promotion, automatic application-endpoint rotation, and
coordinated recovery by multiple application workers after promotion.

It verifies one PostgreSQL 16 physical primary and standby, one test-only stable
TCP endpoint, two competing failover-controller processes, one local witness
lease, a monotonically increasing fence epoch, destructive removal of the
stopped old-primary container, automatic standby promotion, exact same-key
recovery through the unchanged application database URL, and a staged
six-worker convergence corpus on the promoted primary.

The implementation uses production migrations and the production
`accept_repair_proposal_with_source_guard` service. It does not fabricate
acceptance rows, replacement schedules, lifecycle events, PostgreSQL promotion,
WAL replay, or client database errors.

## Starting physical-replication authority

The dedicated workflow reuses the reviewed physical cluster setup:

- one PostgreSQL 16 primary;
- one physical streaming standby built with `pg_basebackup -Fp -Xs -P -R`;
- separate data volumes and one private Docker network;
- observed primary `pg_stat_replication.state = streaming`;
- observed standby `pg_stat_wal_receiver.status = streaming`;
- primary `pg_is_in_recovery() = false`;
- standby `pg_is_in_recovery() = true`;
- one shared nonempty `system_identifier`.

Replication trust is limited to Docker `samenet`; unrestricted
`0.0.0.0/0` replication trust is forbidden by contract.

## Stable application endpoint

A test-only TCP router listens on one application-visible host and port. Its
atomically replaceable state contains only:

- a nonnegative route epoch;
- bounded target label;
- target host;
- target port;
- winner controller identity after failover.

Each new PostgreSQL connection resolves the current target state exactly once.
The router records connection-open, connection-close, route label, and epoch
events, but never records SQL, parameters, database credentials, request
payloads, idempotency keys, or domain identifiers.

The same SQLAlchemy engine URL is used before and after promotion. The
application does not receive a replacement URL and no DNS mutation is involved.
This proves stable-endpoint target rotation for fresh connections, not survival
of already-open database sessions.

## Ambiguous committed request before failure

The application creates a repair proposal through the stable endpoint. The
existing PostgreSQL protocol proxy then forwards a production acceptance
transaction through that same endpoint with `synchronous_commit=on`.

PostgreSQL emits `CommandComplete(COMMIT)`, but the acknowledgement is withheld
from the initiating client. The resulting invalidated `OperationalError` is
classified as:

- `code=database_commit_outcome_unknown`;
- `retryable=true`;
- `retry_safe=false`;
- `outcome_unknown=true`;
- `automatic_retry_performed=false`.

Independent primary reads prove one committed acceptance lifecycle. The test
records `pg_current_wal_flush_lsn()` and waits until
`pg_last_wal_replay_lsn()` on the standby is at or beyond that exact position.
Hot-standby reads prove the same acceptance and replacement identities before
failure injection.

## Automatic failure detection

Two independently identified controller processes begin monitoring the direct
old-primary endpoint while it is healthy. Both must remain alive before the test
injects primary failure.

The old primary is then stopped with zero grace time. A controller may attempt
failover only after at least **three consecutive failed TCP health probes**.
Successful probes reset the consecutive-failure counter.

The HTTP application server still performs no automatic mutation retry. The
controllers manage database topology only; authoritative request recovery occurs
later through the original idempotency key.

## Single-witness promotion authority

Both controllers share one local witness lock file and one witness-state file.
They attempt a nonblocking exclusive `flock` after detecting primary failure.

Exactly one controller may become the promotion winner:

1. It acquires the witness lease.
2. It verifies the stable route still targets `original-primary`.
3. It advances the fence epoch from `0` to `1`.
4. It writes `promotion_in_progress` with its controller identity.
5. It performs the old-primary fence.
6. It promotes the standby.
7. It atomically rotates the stable route to `promoted-standby` at epoch `1`.
8. It publishes the completed `promoted` witness state.

The other controller either observes lease contention and waits for the
completed witness or acquires the lease after completion and reports an
already-promoted no-op. It must not promote or rotate the route.

This is a deterministic **single-host witness lease**, not distributed
consensus, quorum, a replicated lease, or a production control plane.

## Controlled old-primary fence

Promotion is forbidden while Docker reports the old-primary container running.
After failure detection, the winning controller requires that the container
exists but is stopped, then removes that container with `docker rm -f`.

It proves:

- the old container existed before fencing;
- it was not running at fencing time;
- the old container no longer exists afterward;
- the old-primary host endpoint is unavailable;
- the old-primary data volume remains present for forensic recovery.

Container removal prevents that exact old server process definition from being
restarted during the corpus. Retaining the volume is not safe rejoin evidence.
This controlled action is not hardware STONITH, cloud-instance fencing,
Kubernetes fencing, quorum, lease replication, or split-brain prevention under
network partition.

## Promotion and route rotation

The winner invokes `pg_promote(true, 60)` on the standby and waits until:

- `pg_is_in_recovery() = false`;
- `transaction_read_only = off`;
- the original `system_identifier` remains unchanged;
- the promoted WAL timeline differs from the original primary timeline.

Only after those checks does it atomically replace the router state with:

- epoch `1`;
- target label `promoted-standby`;
- the promoted server host and port;
- the winner controller identity.

The stable endpoint event ledger must contain successful connections to
`original-primary` at epoch `0` and `promoted-standby` at epoch `1`.

## Exact recovery through the unchanged URL

After automatic route rotation, the original SQLAlchemy engine object opens a
fresh connection through the same stable URL. It observes the promoted server as
a writable primary with the same cluster system identifier and a new timeline.

The application repeats the exact original proposal ID, actor, payload, and
idempotency key through the production source guard. The promoted primary must
return:

- the original acceptance ID;
- the original draft replacement schedule ID;
- the original idempotency key;
- schedule status `draft`;
- schedule version `1`.

Final authoritative counts remain exactly one acceptance, one replacement, one
proposal `accepted` event, and one replacement `created` event, with proposal
event order `created → accepted`.

## Six-worker recovery after automatic promotion

The workflow keeps the same promoted cluster alive after the first recovery
request. A second integration probe requires the fenced old-primary container to
remain absent and connects directly to the promoted server to discover the one
persisted acceptance lifecycle.

It then starts a fresh stable endpoint whose route is fixed to
`promoted-standby` at epoch `1`. Six independent application worker processes
reuse the reviewed multi-instance recovery helper. Each worker creates:

- a distinct 32-character worker-instance identity;
- a private SQLAlchemy engine, one-connection pool, and session;
- a distinct simultaneously live PostgreSQL backend PID;
- the exact original acceptance payload and idempotency key.

All six workers wait behind one parent-controlled release gate. The gate opens
once, and every worker invokes the production source-level guard concurrently
through the promoted stable endpoint.

The corpus requires all workers to return:

- the same original acceptance ID;
- the same original replacement schedule ID;
- schedule status `draft` and version `1`;
- confirmation that the original idempotency key was preserved;
- `pool_checked_out_after_close = 0`.

Final authoritative counts remain one acceptance, one replacement, one accepted
proposal event, and one created schedule event. The stable endpoint event ledger
must show every worker connection using `promoted-standby` at epoch `1`, and the
router must report zero leaked connection threads.

This proves controlled multi-application-instance convergence after automatic
promotion. Six workers are a deterministic correctness corpus, not
representative production traffic, availability, throughput, or capacity.

## Deterministic process and infrastructure cleanup

The tests collect every controller and worker subprocess output exactly once
with bounded timeouts. Any remaining controller, worker, or router process is
killed and reaped during failure cleanup.

Both stable-router stages report zero leaked connection threads. The workflow
always removes the standby container, retained old-primary volume, standby
volume, and private Docker network. The primary container may already be absent
because the winner fenced it.

## Retained evidence

The dedicated workflow retains:

- JUnit automatic-failover integration evidence;
- a sanitized automatic-failover JSON report;
- a sanitized six-worker post-promotion JSON report;
- Docker process inventory on failure;
- primary and standby logs when available.

The JSON reports contain no database URL, password, SQL, request payload,
idempotency key, or household/user/proposal/schedule identifier.

Configured evidence is not a hosted-green claim until the exact workflow run
and artifacts are observed.

## Non-claims

This controlled automatic failover does **not** establish:

- distributed consensus or a replicated witness;
- production-grade quorum, leases, fencing tokens, or leadership transfer;
- hardware, cloud, hypervisor, Kubernetes, or storage-level STONITH;
- split-brain prevention under asymmetric network partition;
- safe old-primary `pg_rewind`, rebuild, demotion, or rejoin;
- automatic DNS, virtual-IP, service-mesh, cloud-proxy, or managed-database
  endpoint behavior;
- continuity of already-open connections or transparent transaction replay;
- synchronous-standby acknowledgement or zero-loss durability without the
  explicit replay-LSN check;
- multiple-standby selection, cascading replicas, or multi-region failover;
- representative RPO, RTO, availability, latency, throughput, or capacity;
- production operations readiness, clinical validity, food safety, or actual
  preparation execution;
- current hosted workflow success without exact observed evidence.

The combined corpus proves one failure-triggered, single-witness, destructively
fenced promotion from a caught-up physical standby, automatic stable-route
rotation, exact idempotent recovery through the unchanged application URL, and
six-worker exact convergence on the promoted primary.
