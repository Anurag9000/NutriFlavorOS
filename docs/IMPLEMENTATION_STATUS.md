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

Governed research inventory: 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

A class, endpoint, committed test, configured workflow, synthetic fixture, or catalog row is not by itself a readiness, quality, clinical-validation, food-safety, execution-verification, or green-build claim.

## Identity and household collaboration

### Implemented

- Argon2 password hashing, signed JWTs, and weak-secret refusal.
- Explicit profile completion.
- Owner/editor/viewer roles with `404` non-disclosure.
- Hashed email-bound, expiring, single-use invitations.
- Linked and planning-only household members.

### Remaining

Verified email, password reset, MFA, refresh-token rotation/revocation, authentication rate limits, ownership transfer, household archive/delete, complete household export/delete, and support case management.

## Database, migrations, and release integrity

### Implemented

- Reviewed Alembic head `20260802_0018` and exact runtime schema verification.
- Fresh SQLite and PostgreSQL migration workflows.
- API/OpenAPI/repository release-identity validation.
- Migration `0018` duplicate-data preflight and source-version acceptance uniqueness.
- SQLAlchemy model and Alembic migration parity for `uq_preparation_repair_acceptance_source_version`.
- Populated PostgreSQL `0017 → 0018` rehearsal with **64 valid accepted lifecycles** created through production services, exact identity/hash preservation, PostgreSQL catalog verification, and lower-level bypass rollback.
- Sanitized operational-database response boundary with distinct `retryable` and `retry_safe` semantics.
- Immutable hashes, optimistic versions, append-only events, request fingerprints, and idempotency constraints.

### Remaining

Observe exact current hosted workflow runs/artifacts; add production-snapshot or production-scale rehearsal, backup/restore, point-in-time recovery, multi-node failover, pool behavior under sustained load, signed releases, SBOM/provenance attestations, and deployment runbooks.

## Transactional household food state

### Implemented

Versioned pantry lots/leftovers, append-only events, FEFO allocation, expired-stock exclusion, reservations, overbooking prevention, shopping reconciliation, batch grouping, exact idempotency, and PostgreSQL races.

### Remaining

Recall/quarantine, lot split/merge, reviewed receipt/barcode ingestion, pending orders, delivery windows, substitution/pack-size/price optimization, offline reconciliation, and complete export/delete.

## Deterministic meal planning and plan lifecycle

### Implemented

Hard restrictions, household targets, quantity-aware objectives, persisted plans, shopping/reservations, Pareto, optional CP-SAT/MILP, robust/exact comparators, draft/approved/cancelled lifecycle, owner approval, cancellation consequences, append-only events, and exact approved source-plan references.

### Remaining

Independent persisted occurrence-confirmation history, joint meal/inventory/preparation repair, and production-quality stochastic planning.

## Preparation scheduling and repair computation

### Implemented

Explicit capacities/windows/deadlines/priorities/dependencies/provenance; continuous-window enforcement; heuristic/exact semantic parity; reviewed resource calendars; complete occurrence/profile/request/response provenance; combined hashes; deterministic replay; schedule lifecycle; greedy minimal-change repair; bounded exact comparator; immutable anchors; predecessor closure; structured conflicts; authenticated API; offline CLI; and permanent advisory non-acceptance/non-persistence fields.

### Remaining

Larger exact/relaxation comparators, unsat cores, LNS/decomposition, representative optimality-gap/latency/memory evidence, execution-aware repair, joint meal/lot/reservation/shopping/leftover/preparation repair, and minimal conflict explanations.

## Repair proposals, acceptance, invalidation, and approval

### Implemented

- Immutable server-recomputed proposals and append-only events.
- Exact source/calendar/plan/occurrence/profile and repair hashes.
- Complete-only proposal persistence.
- Exact creation/acceptance/rejection/invalidation idempotency.
- Exact changed-task acknowledgement.
- Acceptance that creates one new draft only and never mutates the source.
- Separate owner approval with locked cross-record validation and method-aware replay.
- Tamper, staleness, source execution, plan, calendar, and provenance rejection.

### One accepted replacement per source schedule version

**One accepted replacement per source schedule version** is enforced by migration `20260802_0018`. Multiple advisory proposals may exist, but only one may create a replacement. Competing proposals or keys return the winning proposal, acceptance, and replacement identities.

### Owner-only proposal invalidation

**Owner-only proposal invalidation** is implemented through an authenticated endpoint, typed frontend client, and protected administration workspace. It closes only a `proposed` record, requires exact version/reason/acknowledgement/idempotency, records server-observed stale reasons, creates no schedule, and leaves editors/viewers read-only.

### Remaining

Execution-aware lifecycle semantics after task history exists, multi-node database failover evidence, and production operational monitoring.

## Schedule derivation evidence

### Implemented

**Schedule derivation evidence** distinguishes original and accepted repair-derived schedules through per-schedule and household coverage endpoints. It cross-checks proposal, acceptance, source, calendar, acknowledgement, method, and hash evidence. The protected inspector displays denominators, ratios, incomplete-chain warnings, identities, and hashes.

### Remaining

Embed derivation evidence in additional mutation responses and signed/retained external evidence packages.

## User-confirmed task execution and completion

### Implemented

- Append-only start/complete/skip events.
- Schedule-derived task identity, actual minutes, deviations, mandatory reasons, dependency and chronology guards.
- Optimistic versions and exact retries.
- Product completion only after every deterministic task is terminal.

### Lowest-layer task terminality

**Lowest-layer task terminality** is implemented in the exported `transition_schedule` authority. Direct completion before terminal evidence returns `schedule_tasks_not_terminal`; existing error precedence is preserved; static validation forbids lower-level bypass; and a real PostgreSQL race proves schedule completion cannot commit ahead of the final task event.

### Task-execution eligibility

**Task-execution eligibility** returns `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement` before frontend mutation. A replaced source remains readable but cannot receive task events or completion. Backend guards remain authoritative.

### Remaining

Authenticated PostgreSQL-backed browser evidence and execution-aware repair.

## Preparation schedule support export

### Implemented

The viewer-authorized **Preparation schedule support export** endpoint, operator CLI, typed GET-only client, and protected browser workspace produce one strict, hash-addressed, read-only schedule evidence package.

- Includes schedule provenance, lifecycle events, derivation, execution eligibility, deterministic task state/history, related proposals, acceptances, and proposal events.
- PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, and `txid_current_snapshot()`.
- Canonical SHA-256 excludes transaction timestamps/snapshot metadata but binds all domain evidence and non-claim fields.
- Explicit fields remain `mutation_performed=false`, `actual_execution_verified=false`, and `food_safety_verified=false`.
- The request session requires viewer access and preserves `404` non-disclosure.
- PostgreSQL repeats viewer authorization inside the exact read-only evidence snapshot; the user ID is server-derived.
- The operator CLI remains a separate privileged path and writes atomically.
- The browser provides **explicit support-evidence generation/download**, clears stale scope, restores focus, downloads complete hash-addressed JSON, revokes object URLs, and uses no browser storage or mutation method.
- SQLite/API regressions prove complete evidence chains, owner success, nonmember `404`, operator-path separation, and no export-created rows.
- A real PostgreSQL concurrent-acceptance race proves an existing export retains the pre-acceptance snapshot while a fresh export sees the accepted replacement and a different evidence hash.

### Remaining

Signed/encrypted packages, configurable redaction, retention policy, secure object storage, support-case linkage, download audit events, size/pagination/streaming limits, and production load evidence.

## Database transient failures and exact recovery

### Implemented

**Database transient failures and exact recovery** include:

- SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return sanitized HTTP `503` responses with `database_transaction_retry_required`, `Retry-After: 1`, and same-key guidance.
- Connection exceptions (`08xxx`) and invalidated connections return `database_commit_outcome_unknown`.
- `retryable=true` means exact client retry is prescribed. Proven transaction aborts report `retry_safe=true`; connection ambiguity reports `retry_safe=false`.
- No automatic retry occurs in the exception handler.
- Real **statement-timeout evidence** forces SQLSTATE `57014`, rolls back, and proves a fresh exact retry creates one accepted draft.
- Real **deadlock evidence** creates an actual row-lock/advisory-lock cycle, requires one `40P01` victim, and proves exact retry converges to one acceptance and replacement.
- Lost-response evidence discards committed responses for acceptance, invalidation, and completion, then proves exact same-key recovery without duplicates.
- Real **post-commit connection-loss evidence** terminates the service backend after commit but before response materialization, classifies the outcome as unknown, independently proves one committed lifecycle, and recovers through exact retry.
- Real **checked-out pool connection invalidation evidence** terminates an already checked-out worker before mutation, requires `connection_invalidated=true` and `retry_safe=false`, proves zero mutation, obtains a different fresh backend PID, and converges to one acceptance plus exact retry identity.

### Remaining

Connection loss while COMMIT acknowledgement itself is in flight, PostgreSQL failover, sustained pool exhaustion and recovery, repeated serialization failures, bounded client retry policy, and SQLSTATE/retry/ambiguous-outcome/pool/lock-wait metrics and alerts.

## Provenance, frontend, and research

### Implemented

Preparation operations and derivation coverage expose explicit denominators and malformed/incomplete-chain warnings. Protected frontend workflows cover plan review, occurrence confirmation, calendars, persistence/approval, advisory repair, proposal lifecycle, derivation, execution eligibility, task execution, and support export. The governed research platform retains explicit task/dataset/model/experiment/feature contracts and offline baselines.

### Remaining

Authenticated PostgreSQL-backed Playwright, axe, keyboard/reflow/contrast evidence across all workflows, signed/redacted support download verification, full generated-client parity, alerting/SLOs, household-level signed bundles, and support dashboards.

## PostgreSQL concurrency evidence

### Configured

Real PostgreSQL-only fixtures cover duplicate/competing acceptance; acceptance versus rejection/invalidation/source execution; plan cancellation and calendar supersession races; final-task versus schedule completion; repeatable-read support export; duplicate owner approval; discarded responses; post-commit backend termination; checked-out pooled connection invalidation; statement timeout; genuine deadlock; populated `0017 → 0018` migration rehearsal; and exact migration/dialect assertions with retained JUnit/JSON artifacts.

### Evidence status

The exact latest hosted executions and retained artifacts have not been observed in this context. Configured tests are not reported green until inspected.

## Non-claims

NutriFlavorOS does not establish clinical validity, allergy or medication safety, food safety, contamination state, temperature compliance, actual task performance, human presence, appliance condition, global repair optimality, COMMIT-acknowledgement-in-flight recovery, multi-node failover recovery, sustained pool-load recovery, signed/export-retention guarantees, or current hosted green-build status.
