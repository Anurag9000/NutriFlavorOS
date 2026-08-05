# Controlled Old-Primary Rewind and Standby Rejoin

## Purpose

This boundary extends the controlled automatic-failover corpus after the old
primary has been stopped, fenced by container removal, and replaced by the
promoted physical standby.

It verifies that the retained old-primary data volume can be rebuilt with
PostgreSQL `pg_rewind`, configured as a read-only physical standby of the
promoted primary, returned to active streaming replication, and caught up to a
new WAL position without changing the authoritative application write route or
duplicating the preparation-repair lifecycle.

## Rewind prerequisite

The initial primary starts with and verifies:

`wal_log_hints=on`

This is required because the corpus does not assume data checksums. The setting
ensures the old primary is an eligible `pg_rewind` target after timeline
divergence.

The physical cluster still requires:

- PostgreSQL 16;
- active physical streaming replication before failure;
- one shared nonempty `system_identifier`;
- private-network replication trust through Docker `samenet`;
- exact standby replay-LSN catch-up before promotion.

## Starting authority after automatic failover

The rewind stage runs only after:

- automatic failure detection has completed;
- one controller has won the local witness lease;
- the old-primary container has been removed;
- the old-primary data volume remains present;
- the caught-up standby has been promoted and is writable;
- the promoted server is on the new WAL timeline;
- exact same-key recovery and six-worker post-promotion convergence have left
  one acceptance lifecycle authoritative.

If the old-primary container still exists, rewind authority is denied.

## `pg_rewind` operation

A one-shot PostgreSQL 16 container mounts the retained old-primary data volume
and runs `pg_rewind` as the PostgreSQL operating-system user.

The source server is the promoted primary. The rewind operation uses a normal
superuser database connection with a finite test credential supplied through
the process environment. The generated standby configuration uses the reviewed
`replicator` role and the existing private-network replication rule.

After rewind:

- any stale `recovery.signal` is removed;
- `standby.signal` is created;
- `primary_conninfo` targets the promoted primary container;
- the application name is `rewound-old-primary`;
- the old data volume is started under a distinct rejoin container name and
  host port.

The original fenced container is not restarted.

## Streaming rejoin proof

The bootstrap requires all of the following before success:

- the rejoined server accepts connections;
- `pg_is_in_recovery() = true` on the rejoined node;
- `pg_stat_wal_receiver.status = streaming` on the rejoined node;
- the promoted source has exactly one `pg_stat_replication` row with state
  `streaming` and application name `rewound-old-primary`;
- promoted primary and rejoined standby expose the same nonempty
  `system_identifier`.

The rejoined node is never promoted during this corpus.

## Lifecycle identity and new WAL catch-up

The verifier requires the promoted primary to remain writable and the rejoined
node to report `transaction_read_only = on`.

Both servers must expose exactly one:

- repair-proposal acceptance;
- repair-derived replacement schedule;
- proposal `accepted` event;
- replacement schedule `created` event.

The acceptance ID and replacement schedule ID must match exactly.

The promoted primary then executes a controlled `pg_switch_wal()` and records
`pg_current_wal_flush_lsn()`. The rejoined standby must advance
`pg_last_wal_replay_lsn()` to at least that exact position while remaining in
recovery. Lifecycle counts must still remain one after catch-up.

This proves continuing replication after rejoin, rather than only successful
startup from a rewound snapshot.

## Application-route boundary

The rejoin stage does not alter the stable application write route. The promoted
primary remains the sole write authority, and the rewound node remains a
read-only standby.

No preparation-repair mutation is issued against the rejoined node. The stage
records `application_write_route_changed=false` and
`rejoined_node_promoted=false`.

## Retained evidence and cleanup

The dedicated automatic-failover workflow retains a sanitized rejoin JSON
report with the earlier JUnit, topology JSON, and six-worker JSON evidence.

The report includes only bounded replication, identity, count, and non-claim
fields. It contains no database URLs, passwords, SQL text, request payload,
idempotency key, or domain identifier.

The unconditional cleanup removes the optional rejoin container, promoted
container, retained old-primary volume, standby volume, and private network.

## Non-claims

This controlled rewind and rejoin does **not** establish:

- automatic rejoin orchestration;
- production old-primary lifecycle management;
- distributed consensus, quorum, or replicated fencing authority;
- hardware, cloud, storage, hypervisor, or Kubernetes STONITH;
- partition-safe stale-primary rejection or split-brain prevention;
- safe rejoin when WAL needed by `pg_rewind` has been removed;
- base-backup fallback when rewind is impossible;
- multiple old-primary or standby selection;
- synchronous-replica durability;
- application read routing to the rejoined standby;
- promotion of the rejoined standby;
- representative recovery time, RPO, RTO, throughput, availability, or
  production capacity;
- managed-service, regional, or multi-region behavior;
- current hosted workflow success without exact observed evidence.

The corpus proves one fenced old-primary data volume can be rewound against the
promoted PostgreSQL 16 primary, restarted under a distinct identity as a
read-only streaming standby, and caught up to a new WAL position while the one
accepted preparation-repair lifecycle remains authoritative.
