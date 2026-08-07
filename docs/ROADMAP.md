# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-05  
**Execution rule:** implement directly on `main` in coherent commits; keep code, tests, migrations, contracts, frontend clients, CI, and documentation synchronized; never rewrite history.  
**Current migration head:** `20260802_0018`  
**Current API:** `0.15.4`  
**Current OpenAPI contract:** `2026-08-03.2`

Catalog boundary: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts. Configured work is not executed evidence by itself.

## Completed milestones

### C1–C5 — Transactional household planning and deterministic preparation

Authentication, household roles, pantry/leftover transactions, reservations, quantity-aware meal planning, plan lifecycle, reviewed preparation evidence, deterministic scheduling/replay, hashes, optimistic versions, exact idempotency, and minimal-change repair are implemented.

### C6 — Repair proposal and accepted-draft lifecycle

The **one-replacement-per-source invariant is implemented** by migration `20260802_0018`. Immutable proposals, exact changed-task acknowledgement, one-new-draft acceptance, source immutability, separate method-aware approval, append-only evidence, and the populated 64-lifecycle migration rehearsal are implemented.

### C7 — Derivation and execution authority

**Schedule derivation evidence is implemented** through per-schedule and household coverage endpoints. **Task-execution eligibility is implemented** as backend authority. **Lowest-layer task terminality** prevents schedule completion before explicit terminal task evidence.

### C8 — Proposal invalidation authority

**Owner-only proposal invalidation is implemented** with exact version/idempotency, stale-reason capture, append-only events, role enforcement, and PostgreSQL terminal-outcome races.

### C9 — Lowest-layer schedule completion authority

Exported `transition_schedule` enforces task terminality and PostgreSQL race evidence prevents completion from committing ahead of the final task event.

### C10 — PostgreSQL lifecycle, migration, and recovery evidence

Configured evidence includes lifecycle races, `0017 → 0018` migration rehearsal, timeout/deadlock recovery, lost responses, **post-commit connection-loss recovery**, **checked-out pool connection recovery**, and bounded exact serialization retry. Three consecutive `40001` aborts precede one exact result. Connection ambiguity is reported as `database_commit_outcome_unknown` with `retry_safe=false`; the HTTP server reports `automatic_retry_performed=false`.

### C11 — Read-only support evidence export

A viewer-authorized endpoint, CLI, typed client, and protected workspace provide hash-addressed support evidence. PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, and snapshot-internal authorization.

### C12 — Database recovery observability foundation

The **database recovery observability** foundation uses privacy-preserving process metrics and deterministic OpenMetrics rendering with bounded labels, immutable snapshots, finite-value validation, alerts, and concurrent-update evidence. SQL, request data, keys, and domain IDs are excluded. Cross-replica aggregation, persistent windows, paging, SLOs, and runbooks remain.

### C13 — Controlled PostgreSQL pool exhaustion recovery

SQLAlchemy pool timeout maps to `database_pool_timeout`, `no_transaction_started=true`, and `retry_safe=true`. A one-connection PostgreSQL pool proves zero lifecycle mutation before exact-key recovery.

### C14 — Controlled sustained PostgreSQL pool pressure

The **controlled sustained pool pressure** corpus uses a two-connection pool, three synchronized waves, eight callers per wave, and 24 checkout timeouts. Every failure occurs before transaction start, leaves zero mutation, and releases to `checkedout() == 0`. This is not **representative production capacity**.

### C15 — Controlled application-worker recycle

A **controlled application-worker recycle** closes its occupied pool, proves the old backend disappears, starts a distinct worker/backend, recovers the exact request, and leaks no checkout.

### C16 — Controlled ungraceful application-worker crash

A real **ungraceful application-worker crash** corpus uses `SIGKILL` during checkout and after a flushed open transaction but before COMMIT. PostgreSQL rolls the uncommitted lifecycle back; a fresh worker recovers once.

### C17 — PostgreSQL COMMIT acknowledgement loss

A controlled **COMMIT acknowledgement loss** proxy forwards the complete COMMIT, observes `CommandComplete(COMMIT)`, withholds the acknowledgement, returns outcome-unknown semantics, and proves exact same-key recovery without duplication.

### C18 — Controlled multi-application-instance exact recovery

Six independent application workers establish distinct identities, pools, sessions, and simultaneously live PostgreSQL backends on one primary. One gate releases the exact request; all workers return one shared acceptance and replacement identity and close without pool leakage.

### C19 — Controlled PostgreSQL physical-standby promotion

**Controlled PostgreSQL physical-standby promotion** uses PostgreSQL 16 physical streaming replication, one shared system identifier, observed sender/receiver streaming state, replay-LSN catch-up, original-primary stop, promoted writable standby, a **new WAL timeline**, and exact recovery after explicit endpoint rotation. It does not by itself establish **automatic failover** or **split-brain** prevention.

### C20 — Controlled automatic PostgreSQL failover

**Controlled automatic PostgreSQL failover** keeps one stable application URL for fresh connections. Two controllers require three consecutive failed probes. A **single local witness lease** selects one winner, advances the **fence epoch** from `0` to `1`, removes the stopped old-primary container while retaining its data volume, promotes the caught-up standby, and atomically routes epoch `1` to the promoted primary. The losing controller performs no topology mutation. Exact-key recovery returns the original identities.

This is one single-host control-plane corpus, not **distributed consensus**, replicated quorum, production STONITH, partition-safe fencing, cross-host old-primary rejoin, or managed-service behavior.

### C21 — Six-worker recovery after automatic promotion

A **six-worker post-promotion** corpus runs on the same C20 promoted cluster before teardown.

- The old-primary container remains absent.
- A fresh stable route targets `promoted-standby` at epoch `1`.
- Six independent workers create distinct identities, private pools, sessions, and simultaneously live promoted-primary backend PIDs.
- One gate releases all exact-key requests through the production source guard.
- Every worker returns the original acceptance and replacement identities, confirms the key, and closes with zero checked-out connections.
- Final lifecycle and event counts remain exactly one.
- A sanitized post-promotion JSON report is retained beside the automatic-failover JUnit and topology report.

This closes controlled multi-application-instance convergence after automatic promotion. Six workers remain a correctness corpus, not representative production capacity.

### C22 — Controlled old-primary rewind and standby rejoin

The retained fenced old-primary data volume is rebuilt with PostgreSQL `pg_rewind` after the C20/C21 promoted-primary evidence.

- The initial primary starts with and verifies `wal_log_hints=on`.
- Rewind is denied while the old-primary container exists.
- `pg_rewind` uses the promoted primary as source and the retained old data volume as target.
- The rewound data starts under a distinct container identity with `standby.signal` and replication application name `rewound-old-primary`.
- The node rejoins as a **read-only streaming standby**, while the promoted primary remains the write authority.
- Source and receiver both report streaming and share the same system identifier.
- Acceptance and replacement identities and lifecycle counts remain exactly one on both nodes.
- A controlled `pg_switch_wal()` creates a new flush position, and the rejoined standby must replay at least that exact LSN while remaining in recovery.

This closes one controlled old-primary rewind/rejoin path. C23 adds controlled **automatic rejoin orchestration**; partition-safe stale-primary rejection, missing-WAL fallback, base-backup rebuild, multiple-node lifecycle management, and representative recovery time remain open.

### C23 — Controlled automatic old-primary rejoin

Two simultaneous rejoin controllers automate the reviewed C22 path after the C20/C21 promoted topology is authoritative.

- Both controllers require the old-primary container to remain absent, the promoted primary to be running and writable, the retained old-primary volume to exist, and the rejoin container to be absent.
- Both write atomic ready records and wait behind one release gate.
- One nonblocking local filesystem lease selects one winner and one follower.
- The winner advances rejoin epoch `1`, writes `rejoin_in_progress`, and alone invokes isolated single-user target recovery, `pg_rewind`, stale recovery-setting normalization, standby startup, and the authoritative C22 verifier.
- The follower performs no rewind, no verification, and no topology mutation; it observes the winner identity and completed `rejoined` witness.
- The underlying C22 report remains orchestration-neutral, while the separate C23 summary records automatic orchestration.
- Rejoined read-only streaming state, shared cluster identity, fresh WAL replay, exact acceptance/schedule identities, and lifecycle counts of one remain authoritative.

This closes one single-host automatic rejoin orchestration corpus. It does not establish **distributed consensus**, replicated witness/quorum authority, a cross-host lease, production STONITH, partition-safe stale-primary rejection, controller crash recovery during rewind, missing-WAL/base-backup fallback, or production recovery objectives.

## P0 — Observe and repair exact hosted verification

Inspect exact latest `main` workflow runs and artifacts, record commit/run/artifact identities, repair every failure without skips or weakening, and never report green without exact current evidence.

## P0 — Remaining PostgreSQL operational recovery

- Broader COMMIT-loss timing, encrypted transport, and lower client-buffer behavior.
- Operating-system, container-runtime, Kubernetes pod, and node failure evidence beyond controlled process death.
- Synchronous-standby acknowledgement and durability.
- Distributed or replicated witness/quorum authority, production STONITH, asymmetric-partition fencing, stale-primary write rejection, cross-host rejoin authority, controller crash recovery during rewind, and missing-WAL/base-backup recovery.
- Continuity, invalidation, and pool replacement for already-open sessions during endpoint transition.
- DNS/service-discovery, virtual-IP, service-mesh, managed-proxy, cloud PostgreSQL, multiple standby selection, regional failure, **multi-node failover**, and multi-region recovery.
- Representative RPO, RTO, latency, throughput, traffic, process counts, connection lifetimes, pool sizing, duration, and production capacity.
- Production-snapshot migration rehearsal, backup/restore, and PITR.
- Authenticated production monitoring with rates, cross-replica aggregation, dashboards, paging, SLOs, and runbooks.

The HTTP server never performs automatic mutation retries. Explicit callers retry only when `retry_safe=true`; outcome-unknown requests require authoritative same-key recovery.

## P0 — Browser, accessibility, and support packaging

Add authenticated PostgreSQL-backed Playwright and axe evidence; keyboard, focus, live-region, label, table, reduced-motion, reflow, and contrast evidence; least-privilege support roles; signed/encrypted/redacted packages; retention, revocation, audit linkage, size limits, and production load evidence.

## P1 — Execution-aware and joint repair

Preserve actual task history, replan only remaining work, race execution onset against proposal lifecycle, and jointly repair meals, servings, inventory, reservations, shopping, leftovers, and preparation tasks with explicit human acceptance.

## P2/P3 — Research, operations, and blocked high-risk areas

Continue reviewed evidence, forecasting, constrained ranking, backup/PITR, release engineering, observability, and incident response. Clinical nutrition, medication decisions, allergy guarantees, contamination or food-safety conclusions, autonomous appliance control, autonomous payment, and verified sustainability claims remain disabled without qualified review.

## Non-negotiable release rules

- Advisory computation never reports acceptance or persistence.
- Proposal creation never creates a schedule.
- Acceptance creates one new draft and never implies approval, execution, or completion.
- Invalidation creates no schedule and permanently prevents later acceptance.
- Repair-derived approval requires exact acceptance evidence and method-aware replay.
- Replaced sources remain readable but cannot receive execution events.
- Completion requires lowest-layer terminal task evidence.
- Support export is read-only, hash-addressed, and snapshot-authorized.
- `retry_safe=true` is reserved for proven aborts or proof that no transaction started.
- Connection ambiguity remains `retry_safe=false`; `automatic_retry_performed=false` remains authoritative.
- Recovery metrics never store SQL, request contents, keys, or domain identifiers.
- No clinical, food-safety, global-optimality, representative-capacity, exhaustive-network, distributed-consensus, production-STONITH, cross-host-automatic-rejoin, multi-region, or green-build claim without exact supporting evidence.
- No force push, history rewrite, feature branch, or feature PR.
