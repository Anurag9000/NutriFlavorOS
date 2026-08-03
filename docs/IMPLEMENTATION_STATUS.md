# NutriFlavorOS Implementation Status

**Status date:** 2026-08-03  
**Development policy:** coherent direct commits to `main`; no feature pull requests or development branches; no history rewriting.  
**Database migration head:** `20260802_0018`  
**API version:** `0.15.4`  
**OpenAPI release contract:** `2026-08-03.2`  
**Food-evidence frontend binding contract:** `2026-08-01.2`  
**Preparation-operations frontend binding contract:** `2026-08-02.4`  
**Household-plan frontend binding contract:** `2026-08-02.4`  
**Effective research catalog:** `2026-08-01.3`

Governed inventory: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

Committed code, configured workflows, synthetic fixtures, and catalog rows are not by themselves readiness, clinical-validation, food-safety, execution-verification, or green-build claims.

## Core implemented platform

- Argon2 passwords, signed JWTs, weak-secret refusal, explicit profile completion, and owner/editor/viewer household roles with `404` non-disclosure.
- Transactional pantry lots, leftovers, append-only inventory events, FEFO allocation, reservations, shopping reconciliation, optimistic versions, and exact idempotency.
- Quantity-aware deterministic meal planning, persisted plan lifecycle, owner approval, cancellation consequences, optional CP-SAT/MILP, robust/exact comparators, and approved source-plan references.
- Reviewed preparation profiles and resource calendars, canonical occurrence/profile provenance, deterministic scheduling/replay, combined hashes, and persisted schedule lifecycle.
- Deterministic minimal-change repair with greedy and bounded exact methods, immutable anchors, predecessor closure, structured conflicts, authenticated API, offline CLI, and permanent advisory non-persistence.

## Repair lifecycle

### One accepted replacement per source schedule version

**One accepted replacement per source schedule version** is enforced by migration `20260802_0018`. Multiple advisory proposals may exist, but exactly one may create a replacement. Competing requests return `repair_source_already_has_accepted_replacement` and the winning proposal, acceptance, and replacement identities.

The populated migration rehearsal creates **64 valid accepted lifecycles** through production services at `0017`, upgrades to `0018`, verifies exact identities/hashes/events, checks the live constraint, and proves lower-level bypass rollback.

### Owner-only proposal invalidation

**Owner-only proposal invalidation** is implemented through an authenticated endpoint, typed client, protected administration workspace, exact version/idempotency, server-observed stale reasons, and append-only events. It creates no schedule and leaves editors/viewers read-only.

### Acceptance and approval

Acceptance creates one new draft only, never mutates the source, and requires exact changed-task acknowledgement plus method-aware replay. Owner approval remains separate and revalidates proposal, acceptance, source, plan, calendar, provenance, hashes, and replay under locks.

## Schedule and execution evidence

### Schedule derivation evidence

**Schedule derivation evidence** distinguishes original and accepted repair-derived schedules through per-schedule and household coverage endpoints and a protected inspector. It cross-checks proposal, acceptance, source, calendar, acknowledgement, method, and hashes.

### Lowest-layer task terminality

**Lowest-layer task terminality** is enforced in exported `transition_schedule`. Direct completion before explicit terminal task evidence returns `schedule_tasks_not_terminal`. A real PostgreSQL race proves schedule completion cannot commit ahead of the final task event.

### Task-execution eligibility

**Task-execution eligibility** returns `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement`. Replaced sources remain readable but cannot receive task events or completion. Frontend preflight is explanatory; backend guards remain authoritative.

## Preparation schedule support export

The viewer-authorized **Preparation schedule support export** endpoint, operator CLI, typed GET-only client, and protected browser workspace provide one strict, hash-addressed, read-only evidence package.

- PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, and `txid_current_snapshot()`.
- The request session enforces viewer access, and PostgreSQL repeats viewer authorization inside the exact evidence snapshot.
- The package binds schedule, lifecycle, derivation, eligibility, task history, proposals, acceptances, proposal events, and explicit non-claims.
- The browser provides **explicit support-evidence generation/download**, clears stale scope, restores focus, downloads complete JSON, revokes object URLs, and uses no browser storage or mutation method.
- A real concurrent-acceptance test proves historical and fresh snapshots diverge correctly without export-created rows.

## Database transient failures and exact recovery

**Database transient failures and exact recovery** distinguish client action from proven retry safety:

- `retryable=true` prescribes repeating the exact idempotent request.
- Proven-aborted SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` report `retry_safe=true`.
- Connection exceptions and invalidated connections report `database_commit_outcome_unknown` and `retry_safe=false`.
- SQLAlchemy pool exhaustion before checkout reports `database_pool_timeout`, `no_transaction_started=true`, `retry_safe=true`, and `outcome_unknown=false`.
- The HTTP handler always reports `automatic_retry_performed=false`.

Implemented real PostgreSQL evidence includes:

- **statement-timeout evidence** with `57014`, rollback, and successful exact retry;
- **deadlock evidence** with one `40P01` victim and exact convergence;
- discarded-response exact recovery for acceptance, invalidation, and completion;
- **post-commit connection-loss evidence** using `pg_terminate_backend` after commit and exact same-key recovery;
- **checked-out pool connection invalidation evidence** with `connection_invalidated=true`, `retry_safe=false`, zero pre-recovery mutation, a different fresh backend PID, and one accepted result;
- **bounded exact serialization retry** with finite exponential backoff, immutable observations, exact-key preservation, and no replay of outcome-unknown connections;
- a genuine `SERIALIZABLE` test forcing **three consecutive `40001` aborts** before the fourth exact-key attempt creates exactly one acceptance and replacement;
- controlled **pool exhaustion** using `QueuePool(pool_size=1, max_overflow=0, pool_timeout=0.1)`, zero acceptance/schedule/event mutation before checkout recovery, and exact-key convergence to one accepted replacement.

## Database recovery observability

The **database recovery observability** foundation provides **privacy-preserving process metrics** for sanitized HTTP failures and explicit bounded retry behavior.

- Labels are restricted to `database_transaction_retry_required`, `database_commit_outcome_unknown`, `database_pool_timeout`, `database_operation_failed`, and SQLSTATE buckets `40001`, `40P01`, `57014`, `55P03`, `08xxx`, and `unknown`.
- Snapshots expose operational errors, transaction aborts, outcome-unknown events, nonretryable errors, invalidated connections, retry observations, scheduled retries, successful convergence, exhausted budgets, outcome-unknown utility exits, and total/maximum delay.
- Snapshot mappings are immutable and counters are protected by a re-entrant lock.
- SQL, parameters, exception messages, idempotency keys, household/user/proposal/schedule IDs, food data, and request payloads are never recorded.
- Alert evaluation emits process-local critical/warning values for outcome unknown, retry exhaustion, transaction-abort volume, invalidated connections, and pool checkout timeout.
- Deterministic OpenMetrics rendering uses bounded labels, rejects malformed values, emits one `# EOF`, and exposes no HTTP endpoint.
- Tests prove sanitization, immutable snapshots, handler/retry integration, deterministic alerts, invalid-input atomicity, and 1,600 concurrent updates.

This is an adapter foundation, not production monitoring. Time windows, persistence, **cross-replica aggregation**, dashboards, paging, deduplication, ownership, runbooks, and SLOs remain.

## PostgreSQL concurrency evidence

Configured PostgreSQL-only coverage includes duplicate/competing acceptance, acceptance versus rejection/invalidation/source execution, plan cancellation and calendar supersession races, repaired approval races, final-task versus schedule completion, repeatable-read support export, lost responses, statement timeout, deadlock, post-commit backend termination, checked-out pool invalidation, repeated serialization retry, controlled pool exhaustion, populated migration rehearsal, and exact migration/dialect assertions with retained JUnit/JSON evidence.

The exact latest hosted executions and artifacts have not been observed in this context. Configured tests are not reported green until inspected.

## Remaining P0/P1 work

- Observe and repair exact current hosted workflows and artifacts.
- Test connection loss while COMMIT acknowledgement itself is in flight, multi-node failover, and sustained pool exhaustion/recovery under representative concurrent load.
- Connect process metrics to authenticated production monitoring with cross-replica rates, dashboards, alerts, paging, SLOs, and runbooks.
- Add production-snapshot or production-scale migration rehearsal, backup/restore, and point-in-time recovery.
- Implement authenticated PostgreSQL-backed Playwright, axe, keyboard/reflow/contrast evidence, signed/redacted support packages, retention, and audit linkage.
- Implement execution-aware repair and joint meal/inventory/reservation/shopping/leftover/preparation repair.

## Non-claims

NutriFlavorOS does not establish clinical validity, allergy or medication safety, food safety, contamination state, temperature compliance, actual task performance, human presence, appliance condition, global repair optimality, COMMIT-acknowledgement-in-flight recovery, multi-node failover recovery, production pool sizing or sustained-load capacity, signed/export-retention guarantees, production monitoring completeness, or current hosted green-build status.
