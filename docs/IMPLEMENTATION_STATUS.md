# NutriFlavorOS Implementation Status

**Status date:** 2026-08-05  
**Development policy:** coherent direct commits to `main`; no feature pull requests or development branches; no history rewriting.  
**Database migration head:** `20260802_0018`  
**API version:** `0.15.4`  
**OpenAPI release contract:** `2026-08-03.2`  
**Food-evidence frontend binding contract:** `2026-08-01.2`  
**Preparation-operations frontend binding contract:** `2026-08-02.4`  
**Household-plan frontend binding contract:** `2026-08-02.4`  
**Effective research catalog:** `2026-08-01.3`

Governed inventory: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts. Configured implementation is not automatically executed evidence, clinical validity, food-safety verification, actual-execution verification, production readiness, or current hosted green status.

## Core authority and immutable lifecycle

- Authentication uses Argon2 passwords, signed JWTs, weak-secret refusal, explicit profile completion, and owner/editor/viewer household roles with `404` non-disclosure.
- Pantry lots, leftovers, inventory events, FEFO allocation, reservations, shopping reconciliation, meal planning, plan lifecycle, preparation profiles/calendars, deterministic scheduling/replay, hashes, optimistic versions, and exact idempotency are implemented.
- **One accepted replacement per source schedule version** is enforced by migration `20260802_0018`; the populated migration rehearsal creates **64 valid accepted lifecycles** and proves the one-replacement constraint.
- **Owner-only proposal invalidation** creates no schedule and permanently prevents acceptance.
- Acceptance creates one new draft only; approval remains separate and method-aware.
- **Schedule derivation evidence**, **Task-execution eligibility**, and **Lowest-layer task terminality** are implemented as backend authority with protected frontend inspection.
- **Preparation schedule support export** is viewer-authorized, hash-addressed, PostgreSQL `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, snapshot-authorized, and mutation-free.

## Database transient failures and exact recovery

The HTTP boundary distinguishes prescription from proof:

- SQLSTATE `40001`, `40P01`, `57014`, and `55P03` return `database_transaction_retry_required` with proven-aborted retry safety.
- Invalidated or connection-class failures return `database_commit_outcome_unknown`, `retry_safe=false`, and `automatic_retry_performed=false`.
- Pool checkout timeout returns `database_pool_timeout`, `no_transaction_started=true`, and `retry_safe=true`.
- **Exact classification integrity** and **Nonfinite retry timing** validation fail before counters change.

Configured real PostgreSQL evidence includes:

- statement timeout, deadlock, lost-response replay, **post-commit connection-loss evidence**, and **checked-out pool connection invalidation evidence**;
- **bounded exact serialization retry** with **three consecutive `40001` aborts** before one exact result;
- controlled pool exhaustion and **controlled sustained pool pressure** with **24 checkout timeouts** and **zero lifecycle mutation** before recovery;
- **controlled application-worker recycle** with backend disappearance and same-key recovery;
- **Controlled ungraceful application-worker crash** using real `SIGKILL`, including a **flushed but uncommitted** lifecycle that PostgreSQL rolls back;
- controlled **COMMIT acknowledgement loss**, where PostgreSQL emits `CommandComplete(COMMIT)` and recovery uses the **same exact idempotency key**;
- one-primary six-worker convergence with distinct worker identities, pools, and PostgreSQL backends;
- controlled physical replication, manual promotion, automatic promotion, and six-worker recovery after promotion.

## Controlled physical-standby promotion

The **controlled physical-standby promotion** corpus creates PostgreSQL 16 primary and standby containers through physical streaming replication. Active sender and receiver states are observed, both servers share one nonempty `system_identifier`, and replication trust is limited to Docker `samenet`.

After the acknowledgement-withheld acceptance commits, the primary flush LSN is recorded and the standby **replay-LSN** must reach it. The old primary is stopped, its endpoint becomes unavailable, the standby is promoted with `pg_promote(true, 60)`, becomes writable on a **new WAL timeline**, and **explicit endpoint rotation** recovers the original acceptance and replacement identities without duplication.

## Controlled automatic PostgreSQL failover

The **controlled automatic PostgreSQL failover** corpus keeps one **unchanged stable database URL** and one stable endpoint for fresh application connections.

- Two controllers require three consecutive failed old-primary probes.
- A **single local witness lease** permits exactly one promotion winner.
- The winner advances a **fence epoch** from `0` to `1`.
- Promotion is forbidden while the old primary is running.
- The stopped old-primary container is removed, its data volume is retained, and its endpoint remains unavailable.
- The caught-up standby is promoted, retains the cluster identity, and advances to a new timeline.
- The stable route changes atomically from `original-primary` epoch `0` to `promoted-standby` epoch `1`.
- The original engine opens a fresh connection through the unchanged URL and returns the original acceptance and replacement identities.
- The controllers never retry application mutations; the server remains `automatic_retry_performed=false`.

## Six-worker post-promotion exact recovery

The **six-worker post-promotion** corpus runs on the same automatically promoted cluster before teardown.

- The old-primary container remains absent.
- A fresh epoch-`1` stable route points only to `promoted-standby`.
- Six independent worker processes create distinct 32-character identities, private one-connection pools, sessions, and simultaneously live promoted-primary backend PIDs.
- One release gate opens all six production source-guard calls with the exact original proposal, actor, payload, and key.
- Every worker returns the same acceptance ID and schedule ID, confirms key equality, and closes with `pool_checked_out_after_close=0`.
- Final counts remain one acceptance, one replacement, one accepted event, and one created event in `created → accepted` order.
- The stable router records every worker at epoch `1` and leaks no connection threads.

This closes controlled multi-application-instance convergence after automatic promotion. It is not **representative production capacity**.

## Database recovery observability

The **database recovery observability** foundation provides privacy-preserving process metrics and deterministic OpenMetrics rendering.

- Bounded labels cover reviewed error codes and SQLSTATE buckets only.
- SQL, parameters, exception messages, request contents, idempotency keys, and domain IDs are excluded.
- Immutable snapshots, finite numeric checks, deterministic alerts, and 1,600 concurrent updates are tested.
- No public metrics endpoint exists.

Persistence, time windows, **cross-replica aggregation**, dashboards, paging, ownership, runbooks, and SLOs remain production work.

## PostgreSQL evidence inventory

Configured PostgreSQL-only coverage includes lifecycle races, migration rehearsal, support-export snapshot concurrency, timeout/deadlock recovery, backend termination, pool invalidation, repeated serialization, pool exhaustion and pressure, worker recycle and crash, COMMIT acknowledgement loss, one-primary multi-instance recovery, physical-standby promotion, automatic fenced failover, and six-worker post-promotion recovery. JUnit and sanitized JSON artifacts are configured, but the exact latest hosted executions have not been observed here.

## Remaining P0/P1 work

- Observe and repair exact current hosted workflows and artifacts.
- Broaden COMMIT-loss timing and encrypted-transport evidence.
- Add synchronous-standby acknowledgement, operating-system/container/node failure evidence, distributed or replicated witness/quorum authority, production STONITH, asymmetric-partition fencing, stale-primary write rejection, and safe old-primary `pg_rewind`/rejoin.
- Exercise continuity and invalidation of already-open sessions, DNS/service-discovery and managed-proxy behavior, multiple standby selection, managed/cloud PostgreSQL, regional failure, and **multi-node failover** or multi-region recovery.
- Establish representative traffic, capacity, RPO, RTO, latency, throughput, duration, backup/restore, PITR, and production-scale migration evidence.
- Complete authenticated production monitoring, browser/axe/accessibility evidence, signed/redacted support packages, retention/audit linkage, and execution-aware joint repair.

## Non-claims

NutriFlavorOS does not establish clinical validity, allergy or medication safety, food safety, contamination or temperature compliance, actual task performance, human presence, appliance state, global repair optimality, exhaustive COMMIT-loss recovery, encrypted-transport interception, synchronous-standby durability, distributed consensus, replicated quorum or witness correctness, production STONITH, asymmetric-partition split-brain prevention, safe old-primary rejoin, already-open-session continuity, managed-database or multi-region behavior, representative production capacity, production pool sizing, signed-package guarantees, production monitoring completeness, or current hosted green-build status.
