# NutriFlavorOS Engineering and Research Roadmap

**Roadmap date:** 2026-08-04  
**Execution rule:** implement directly on `main` in coherent commits; keep code, tests, migrations, contracts, frontend clients, CI, and documentation synchronized; never rewrite history.  
**Current migration head:** `20260802_0018`  
**Current API:** `0.15.4`  
**Current OpenAPI contract:** `2026-08-03.2`

Catalog boundary: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts. Configured code or tests are not executed evidence by themselves.

## Completed milestones

### C1–C5 — Transactional household planning and deterministic preparation

Authentication, household roles, pantry/leftover transactions, reservations, quantity-aware meal planning, plan lifecycle, reviewed preparation evidence, deterministic scheduling/replay, and minimal-change repair are implemented with optimistic versions, exact idempotency, provenance, hashes, and append-only evidence.

### C6 — Repair proposal and accepted-draft lifecycle

Immutable server-recomputed proposals, exact changed-task acknowledgement, one-new-draft-only acceptance, source immutability, separate method-aware owner approval, and append-only evidence are implemented. The **one-replacement-per-source invariant is implemented** by migration `20260802_0018` and a populated 64-lifecycle migration rehearsal.

### C7 — Derivation and execution authority

**Schedule derivation evidence is implemented** through per-schedule and household coverage endpoints plus a protected inspector.

**Task-execution eligibility is implemented** through a viewer endpoint and frontend gate. Replaced sources remain readable but cannot receive execution events or completion.

### C8 — Proposal invalidation authority

**Owner-only proposal invalidation is implemented** through API, typed client, protected workspace, exact version/idempotency, stale-reason capture, append-only events, role enforcement, and PostgreSQL terminal-outcome races.

### C9 — Lowest-layer schedule completion authority

**Lowest-layer task terminality** is implemented in exported `transition_schedule`. Direct completion requires explicit terminal task evidence, lower-level bypass is forbidden, and a PostgreSQL race proves completion cannot commit ahead of the final task event.

### C10 — PostgreSQL lifecycle, migration, and recovery evidence

Configured evidence includes lifecycle/dependency races, the populated `0017 → 0018` migration rehearsal, statement-timeout and deadlock recovery, discarded-response recovery, **post-commit connection-loss recovery**, **checked-out pool connection recovery**, and **bounded exact serialization retry**.

A genuine `SERIALIZABLE` probe forces **three consecutive `40001` aborts** before the fourth exact-key attempt creates one acceptance and replacement. Connection ambiguity dominates nominal abort SQLSTATEs, and the HTTP server reports `automatic_retry_performed=false`.

### C11 — Read-only support evidence export

A viewer-authorized endpoint, operator CLI, typed GET-only client, and protected workspace provide hash-addressed schedule evidence. PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, snapshot-internal viewer authorization, and canonical hashing. A real concurrent-acceptance race proves snapshot consistency.

### C12 — Database recovery observability foundation

The **database recovery observability** foundation is implemented as privacy-preserving process-local metrics plus deterministic OpenMetrics rendering.

- Only bounded error codes and SQLSTATE buckets are recorded.
- SQL, parameters, exception messages, idempotency keys, domain IDs, food data, and request payloads are excluded.
- Exact code/proof classification and finite numeric values are enforced before counters change.
- Immutable snapshots expose error, retry, convergence, exhaustion, ambiguity, invalidated-connection, pool-timeout, and delay counters.
- Thread-safe aggregation and deterministic alert evaluation include 1,600 concurrent updates.
- OpenMetrics output rejects unreviewed labels and malformed values and exposes no HTTP endpoint.

Persistent time windows, **cross-replica aggregation**, dashboards, paging, deduplication, ownership, runbooks, and SLOs remain.

### C13 — Controlled PostgreSQL pool exhaustion recovery

A real **pool exhaustion** boundary is implemented.

- SQLAlchemy `TimeoutError` maps to `database_pool_timeout`.
- The response reports `no_transaction_started=true`, `retry_safe=true`, `transaction_aborted=false`, `outcome_unknown=false`, and `automatic_retry_performed=false`.
- The explicit bounded utility retries only with the identical idempotency key.
- A PostgreSQL `QueuePool` probe uses `pool_size=1`, `max_overflow=0`, and `pool_timeout=0.1`.
- Independent reads prove zero acceptance, replacement schedule, and lifecycle-event mutation before checkout recovery.
- Releasing the held connection permits exactly one accepted replacement; a later retry returns the same identities.
- A dedicated direct-`main` workflow retains JUnit evidence.

This proves controlled checkout-timeout recovery, not production pool sizing or sustained-load capacity.

### C14 — Controlled sustained PostgreSQL pool pressure

**Controlled sustained pool pressure** is implemented as a deterministic extension of C13.

- A constrained `QueuePool` uses two connections, no overflow, a 0.12-second checkout timeout, and pre-ping.
- Three synchronized waves run eight callers per wave against the same exact idempotent acceptance request.
- All **24 checkout timeouts** prove `no_transaction_started=true`, `retry_safe=true`, and `outcome_unknown=false`.
- Independent reads after every wave prove zero lifecycle mutation.
- Metrics prove exactly 24 retry observations and exhausted single-attempt budgets, with no scheduled retries, ambiguity, or invalidated connections.
- After releasing capacity, `checkedout() == 0`, one exact-key request creates one replacement, a later retry returns the same identities, and the pool returns to zero checked-out connections.

This closes controlled repeated pressure and leak-free recovery. It does not establish **representative production capacity**, safe deployment sizing, real-traffic latency, fairness, or indefinite pressure handling.

### C15 — Controlled application-worker recycle

A **controlled application-worker recycle** is implemented under active pool exhaustion.

- The old subprocess owns a one-connection pool and publishes a stable worker-instance identity plus a live PostgreSQL backend PID.
- Guarded acceptance times out before transaction start and leaves exactly zero lifecycle mutation.
- The parent requests an orderly recycle through stdin.
- The old worker closes its connection, reports zero checked-out connections, disposes its engine, and exits successfully.
- The parent proves the old PostgreSQL backend disappears from `pg_stat_activity`.
- A fresh worker process publishes a different worker-instance identity and backend PID, performs the same exact-key acceptance once, and closes without a pool leak.
- A final retry returns the same acceptance and schedule identities.

### C16 — Controlled ungraceful application-worker crash

A real **ungraceful application-worker crash** boundary is implemented with `SIGKILL`.

- Checkout-holder case: the worker holds the only pool connection, the exact acceptance times out before transaction start, and committed reads prove zero lifecycle mutation before and after process death.
- Flushed-open-transaction case: production acceptance flushes one acceptance, replacement schedule, accepted proposal event, and created schedule event inside the worker transaction; an independent committed reader simultaneously sees zero and the proposal remains `proposed`.
- The parent kills the worker with `SIGKILL`, waits for the old PostgreSQL backend to disappear, and proves the flushed but uncommitted lifecycle is fully rolled back.
- A fresh worker with a different worker-instance identity and backend PID repeats the same exact idempotency key and creates one accepted replacement. The operating-system PID remains diagnostic only because **OS PID reuse** is legal.
- A final retry returns the same acceptance and schedule identities and preserves `created → accepted` proposal-event order.

This closes controlled application-process death during checkout and before commit. It does not establish operating-system/container/node failure behavior, cross-replica recovery, or **multi-node failover**.

### C17 — PostgreSQL COMMIT acknowledgement loss

A controlled **COMMIT acknowledgement loss** boundary is implemented with a test-only PostgreSQL wire proxy.

- The proxied production acceptance transaction sets `synchronous_commit=on`.
- The proxy parses simple-query and extended-protocol messages, arms the drop before forwarding COMMIT, and proves the complete COMMIT frame is forwarded upstream.
- PostgreSQL emits `CommandComplete(COMMIT)`; the proxy withholds that acknowledgement and closes both proxied sockets.
- The client receives an invalidated `OperationalError` classified as `database_commit_outcome_unknown`, `retry_safe=false`, and `automatic_retry_performed=false`.
- Independent direct reads prove one committed acceptance, one draft replacement, and exactly one accepted/created event pair.
- A fresh request with the same exact idempotency key returns the existing acceptance and schedule identities without duplication.
- The proxy proves both forwarding threads terminate without leakage.

This closes one controlled acknowledgement-withheld timing after server-side COMMIT completion. It does not establish all possible network-loss timings, encrypted transport interception, synchronous-replica durability, cross-replica coordination, or **multi-node failover**.

## P0 — Observe and repair exact hosted verification

Inspect exact latest `main` workflow runs and artifacts, record exact commit/run/artifact identities, repair every failure without skip or weakening, and never report green until exact current evidence is observed.

## P0 — Remaining PostgreSQL operational recovery

- Broader network-loss timings around COMMIT, including encrypted transport and loss after acknowledgement reaches lower client buffers.
- Operating-system, container-runtime, Kubernetes pod, and node failure behavior beyond the controlled worker `SIGKILL` corpus.
- PostgreSQL primary loss, replica promotion, DNS/service-discovery changes, synchronous-replica acknowledgement, and multi-node failover.
- Cross-replica retry coordination and process replacement across multiple application instances.
- Representative production capacity under realistic concurrent traffic, queueing, latency, process counts, pool sizing, connection lifetime/recycle behavior, and duration beyond the controlled 24-timeout corpus.
- Production-snapshot or production-scale migration rehearsal beyond the 64-lifecycle corpus.
- Authenticated production monitoring with rates, cross-replica aggregation, dashboards, alerts, paging, SLOs, and runbooks.

The HTTP server never performs automatic mutation retries. Explicit callers may use bounded retry only when `retry_safe=true`; connection ambiguity remains `retry_safe=false` and requires authoritative same-key outcome recovery.

## P0 — Browser, accessibility, and support packaging

Add authenticated PostgreSQL-backed Playwright and axe evidence for the complete lifecycle; keyboard-only, focus, error-summary, live-region, label, table, reduced-motion, zoom/reflow, and contrast evidence; configurable redaction; least-privilege support roles; signed/encrypted packages; verification tooling; secure storage/retention/revocation; support-case and download audit linkage; streaming/size limits; household bundles; and production load evidence.

## P1 — Execution-aware and joint repair

Treat task events as immutable facts, preserve actual history, replan only remaining work, race execution onset against proposal/acceptance/approval, and jointly repair meals, servings, pantry allocations, reservations, shopping, leftovers, and preparation tasks while preserving approved history and explicit human acceptance.

## P2/P3 — Research, operations, and blocked high-risk areas

Continue reviewed evidence, forecasting, constrained ranking, backup/PITR, release engineering, observability/SLOs, and incident response. Clinical nutrition, medication decisions, allergy-safety guarantees, contamination or food-safety conclusions, autonomous appliance control, autonomous procurement/payment, and verified sustainability claims remain disabled without specialist review and qualified evidence.

## Non-negotiable release rules

- Advisory computation never reports acceptance or persistence.
- Proposal creation never creates a schedule.
- Acceptance creates one new draft and never implies approval, execution, or completion.
- Invalidation creates no schedule and permanently prevents later acceptance.
- Repair-derived approval requires exact acceptance evidence and method-aware replay.
- Replaced sources remain readable but cannot receive new execution events.
- Completion requires explicit task terminality at the lowest exported authority.
- Support export is read-only, hash-addressed, snapshot-authorized, and never upgrades user-entered evidence into execution or safety verification.
- `retry_safe=true` is reserved for proven transaction aborts or proof that no transaction started; connection ambiguity remains `retry_safe=false`.
- The server always reports `automatic_retry_performed=false`.
- Database recovery metrics never store SQL, request contents, idempotency keys, or domain identifiers.
- Frontend preflight never replaces server authority.
- No clinical, food-safety, global-optimality, model-readiness, representative-capacity, exhaustive-commit-loss, node-failure, cross-replica, failover, or green-build claim without exact supporting evidence.
- No force push, history rewrite, feature branch, or feature PR.
