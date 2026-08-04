# PostgreSQL COMMIT Acknowledgement Loss

## Purpose

This boundary verifies exact preparation-repair recovery when PostgreSQL commits
a mutation but the client does not receive the COMMIT acknowledgement.

A test-only TCP proxy forwards one real PostgreSQL connection. It detects and
forwards the frontend COMMIT, waits until PostgreSQL produces
`CommandComplete(COMMIT)`, deliberately withholds that acknowledgement from the
client, and closes both sides of the proxied connection. The client therefore
receives a connection failure with an unknown commit outcome even though an
independent direct connection can observe the committed lifecycle.

The test uses the production
`accept_repair_proposal_with_source_guard` service. It does not fabricate an
exception, acceptance, schedule, or lifecycle event.

## Why the outcome is ambiguous to the client

The proxy arms the drop before forwarding the COMMIT frame. It then records two
separate facts:

1. the COMMIT query was detected;
2. the complete COMMIT frame was actually forwarded upstream.

The proxy parses PostgreSQL protocol frames and supports both:

- simple-query messages (`Q`);
- extended-protocol parse messages (`P`).

On the server-to-client direction, it waits for a command-complete message (`C`)
whose tag is exactly `COMMIT`. It consumes that complete frame but does not
forward it. The client connection is then closed before the client receives the
acknowledgement.

The resulting SQLAlchemy `OperationalError` is classified as:

- `code=database_commit_outcome_unknown`;
- `retryable=true`;
- `retry_safe=false`;
- `transaction_aborted=false`;
- `outcome_unknown=true`;
- `retry_same_idempotency_key=true`;
- `automatic_retry_performed=false`.

`retry_safe=false` is essential: the caller must not assume rollback and must
not generate a new idempotency key.

## Commit durability setting

Before invoking production acceptance, the proxied transaction executes:

`SET LOCAL synchronous_commit = on`

and verifies `SHOW synchronous_commit` returns `on`.

The proxy therefore withholds `CommandComplete(COMMIT)` only after PostgreSQL
has completed the local synchronous commit boundary for this transaction. This
is not a statement about synchronous replication because the test service has
no configured synchronous standby.

## Protocol-inspection boundary

Protocol inspection requires an unencrypted test connection. The proxied URL
sets:

- `sslmode=disable`;
- `gssencmode=disable`;
- a finite connection timeout.

This is a test-only boundary against the local PostgreSQL service. It does not
recommend disabling TLS or GSS encryption in production. Production database
connections must follow the deployment security policy.

## Persisted evidence

Before the proxied request, independent direct reads require exactly zero:

- acceptance rows;
- repair-derived replacement schedules;
- proposal `accepted` events;
- replacement schedule `created` events.

After the proxy observes and withholds `CommandComplete(COMMIT)`, independent
direct reads require exactly:

- one acceptance;
- one draft replacement schedule at version 1;
- one proposal `accepted` event;
- one replacement schedule `created` event;
- proposal status `accepted`;
- proposal event order `created → accepted`.

The caller did not receive the acceptance response. A fresh direct request with
the **same exact idempotency key** must return the already-created acceptance
and schedule identities. Counts remain exactly one.

## Proxy cleanup

The proxy uses bounded socket timeouts and dedicated client-to-server and
server-to-client threads. The final report requires:

- COMMIT detected;
- COMMIT forwarded;
- `CommandComplete(COMMIT)` observed;
- acknowledgement not forwarded;
- client connection closed;
- upstream connection closed;
- every proxy thread stopped.

Any protocol parser error or leaked thread fails the test.

## Verification gate

A dedicated PostgreSQL workflow compiles and runs:

- the protocol proxy;
- the real commit-acknowledgement-loss test;
- the transient database-error classifier;
- the production source-acceptance guard;
- the protocol contract;
- the synchronized release validator.

The workflow upgrades PostgreSQL to migration head `20260802_0018`, verifies the
runtime schema, and retains JUnit evidence. Configured execution is not a hosted
green claim until the exact run and artifact are observed.

## Non-claims

This is one **single controlled proxy connection** and does not prove:

- every possible network-loss timing around COMMIT;
- loss before PostgreSQL completes COMMIT;
- loss after the acknowledgement reaches an operating-system or driver buffer;
- TLS- or GSS-encrypted protocol interception;
- synchronous-replica acknowledgement or replication durability;
- PostgreSQL primary loss, replica promotion, DNS changes, or service discovery;
- cross-replica application retry coordination;
- representative production latency, throughput, capacity, or proxy behavior;
- operating-system, container, Kubernetes, or node failure;
- global correctness for non-idempotent mutations;
- clinical, food-safety, actual-execution, or deployment readiness;
- current hosted workflow success without exact observed evidence.

This controlled case **does not prove multi-node failover**. It proves that one
idempotent preparation-repair acceptance can recover authoritatively after the
server completes COMMIT and its acknowledgement is withheld from the client.
