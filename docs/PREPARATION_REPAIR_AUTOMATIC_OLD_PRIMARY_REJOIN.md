# Controlled Automatic Old-Primary Rejoin Orchestration

## Purpose

This boundary automates the already-reviewed C22 old-primary rewind and standby
rejoin path after the C20 automatic promotion and C21 six-worker recovery corpus
have completed.

It does not change the preparation-repair mutation contract. The HTTP server
still performs no automatic mutation retry. The rejoin controller operates only
on PostgreSQL topology after the accepted repair lifecycle is already
committed, replicated, promoted, and recovered by exact idempotency.

## Preconditions

Two independent controller subprocesses must each observe all of the following
before they become ready:

- the fenced old-primary container is absent;
- the promoted PostgreSQL container exists and is running;
- the promoted server reports `pg_is_in_recovery() = false`;
- the promoted server reports `transaction_read_only = off`;
- the retained old-primary Docker volume exists;
- the rejoin container does not yet exist.

These are controlled single-host topology facts. They are not evidence of a
replicated cluster membership service or partition-safe failure detector.

## Simultaneous controller release

The orchestration runner starts exactly two controller processes with distinct
controller identities. Each controller writes an atomic ready record and waits
behind one parent-created release gate.

The gate is opened only after both controllers have published the required
preconditions. This prevents the corpus from silently reducing to a sequential
single-controller invocation.

After release, both controllers contend for one nonblocking POSIX `flock`
lease. The lease and witness live on one local filesystem.

Exactly one controller may become the rejoin winner. The other controller must
either:

- observe lease contention and wait for the completed witness; or
- acquire the lease only after the winner exits, observe that rejoin already
  completed, and perform no mutation.

The follower must report:

- `lease_acquired=false`;
- `rewind_performed=false`;
- `verification_performed=false`;
- `topology_mutation_performed=false`;
- the exact winner controller identity;
- witness status `rejoined` and rejoin epoch `1`.

## Winner authority

The winner rechecks every topology precondition while holding the lease. It
then writes an atomic witness with:

- `status=rejoin_in_progress`;
- `rejoin_epoch=1`;
- its controller identity as the sole winner.

Only the winner invokes the reviewed C22 pipeline:

1. `scripts/rewind_preparation_repair_old_primary.sh`;
2. `scripts/probe_preparation_repair_old_primary_rejoin.py`.

The rewind script must retain all C22 authority checks:

- deny rewind while the old-primary container exists;
- recover the zero-grace stopped target in PostgreSQL single-user mode under
  Docker `--network none`;
- remove the stale `postmaster.pid` only inside that isolated recovery target;
- issue `CHECKPOINT` before rewind;
- run PostgreSQL `pg_rewind` against the promoted source;
- remove stale recovery settings such as preexisting `primary_conninfo` and
  `primary_slot_name`;
- create `standby.signal`;
- start the retained data under a distinct rejoin-container identity;
- require receiver and sender state `streaming`;
- require the same PostgreSQL system identifier.

The controller refuses success unless the script emits every reviewed marker,
including:

- `isolated_target_crash_recovery=true`;
- `stale_recovery_settings_normalized=true`;
- `pg_rewind_completed=true`;
- `rejoin_in_recovery=t`;
- `rejoin_receiver_status=streaming`;
- `promoted_sender_count=1`;
- `shared_system_identifier=true`.

## Authoritative post-rejoin verification

The existing C22 verifier remains deliberately orchestration-neutral and keeps
`automatic_rejoin_orchestration=false` in its own report. It independently
proves:

- the promoted primary remains writable;
- the rewound old primary is in recovery and read-only;
- receiver and sender state are streaming;
- both servers share the same system identifier;
- acceptance and replacement identities are preserved;
- acceptance, replacement, accepted-event, and created-event counts remain one;
- a fresh `pg_switch_wal()` position is replayed by the rejoined standby while
  it remains in recovery.

The automatic controller reads that report and fails closed unless every
reviewed proof is present. Automation authority is recorded only in the
separate C23 summary.

## Evidence partition

The retained automatic-rejoin summary records:

- two controllers ready before release;
- two distinct controller identities;
- one local rejoin lease;
- one winner and one follower;
- rejoin epoch `1`;
- one rewind pipeline;
- one authoritative verification pipeline;
- one read-only streaming rejoined standby;
- preserved acceptance and schedule identities;
- final lifecycle counts exactly one;
- zero topology mutation by the follower.

State, witness, ready, controller, C22 verification, and C23 summary files omit
database passwords, database URLs, SQL text, request payloads, idempotency keys,
and household, user, proposal, acceptance, or schedule identifiers.

## Deterministic process cleanup

The runner collects every controller output exactly once. A timed-out or failed
controller is killed and reaped. The workflow retains reports and diagnostics
and then removes the promoted primary, rejoined standby, volumes, and private
network through the existing unconditional cleanup step.

## Non-claims

This controlled automatic rejoin orchestration does **not** establish:

- distributed consensus;
- a replicated witness or quorum;
- a cross-host lease;
- production STONITH or hardware fencing;
- partition-safe stale-primary rejection;
- correctness under asymmetric network reachability;
- controller crash recovery while `pg_rewind` is in progress;
- lease persistence across host loss;
- missing-WAL fallback;
- automatic base-backup rebuild when `pg_rewind` cannot proceed;
- multiple failed-node lifecycle management;
- Kubernetes operator, Patroni, repmgr, cloud-database, or managed-service
  behavior;
- DNS, virtual-IP, service-mesh, or multi-region topology management;
- representative recovery time, RPO, RTO, throughput, or production capacity;
- current hosted green status without the exact workflow run and artifacts.

The evidence proves only that, on one controlled Linux host after a completed
C20/C21 promotion, two simultaneous local controllers converge on one automatic
execution of the reviewed isolated C22 rewind/rejoin path, and the follower
performs no topology mutation.
