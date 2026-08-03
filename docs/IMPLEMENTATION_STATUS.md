# NutriFlavorOS Implementation Status

**Status date:** 2026-08-03  
**Development policy:** coherent direct commits to `main`; no feature pull requests or development branches; no history rewriting.  
**Database migration head:** `20260802_0018`  
**API version:** `0.15.3`  
**OpenAPI release contract:** `2026-08-03.1`  
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
- Sanitized operational-database response boundary for retryable transaction aborts and ambiguous connection outcomes.
- Immutable hashes, optimistic versions, append-only events, full request fingerprints, and idempotency constraints.

### Remaining

Observe exact current hosted workflow runs/artifacts; add production-snapshot or production-scale rehearsal, backup/restore, point-in-time recovery, multi-node failover, pool invalidation under load, signed releases, SBOM/provenance attestations, and deployment runbooks.

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

## Preparation scheduling

### Implemented

Explicit capacities/windows/deadlines/priorities/dependencies/provenance; continuous-window enforcement; heuristic/exact semantic parity; reviewed resource calendars; complete occurrence/profile/request/response provenance; combined hashes; deterministic replay; and draft/approved/invalidated/completed/cancelled lifecycle.

### Remaining

Larger exact/relaxation comparators, unsat cores, LNS/decomposition, and representative optimality-gap/latency/memory evidence.

## Preparation repair computation

### Implemented

Greedy minimal-change repair, bounded exact comparator, immutable anchors, predecessor closure, revised dependency/deadline/window/capacity validation, structured conflicts, outcome partitions, canonical hashes, authenticated API, offline CLI, and permanent advisory non-acceptance/non-persistence fields.

### Remaining

Execution-aware repair, joint meal/lot/reservation/shopping/leftover/preparation repair, scalable minimum-change optimization, and minimal conflict explanations.

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

**One accepted replacement per source schedule version** is enforced by migration `20260802_0018`. Multiple advisory proposals may exist, but only one may create a replacement draft. Competing proposals or keys return the winning proposal, acceptance, and replacement identities.

### Owner-only proposal invalidation

**Owner-only proposal invalidation** is implemented through an authenticated endpoint, typed frontend client, and protected administration workspace.

- Only `proposed` records can be invalidated.
- Requires expected version, reason, `acknowledge_historical_only=true`, metadata, and idempotency key.
- Server-observed stale reasons are recorded in the append-only event.
- No acceptance, persistence, approval, execution, source mutation, or rejection-field reuse occurs.
- Exact retry is idempotent; contradictory keys, stale versions, and terminal proposals fail closed.
- Editors and viewers remain read-only.

### Remaining

Execution-aware lifecycle semantics after task history exists, multi-node database failover evidence, and production operational monitoring.

## Schedule derivation evidence

### Implemented

**Schedule derivation evidence** distinguishes original and accepted repair-derived schedules through per-schedule and household coverage endpoints. It cross-checks proposal, acceptance, source, calendar, acknowledgement, method, and hash evidence. The protected read-only inspector displays denominators, ratios, incomplete-chain warnings, identities, and hashes.

### Remaining

Embed derivation evidence in additional mutation responses and signed/retained external evidence packages.

## User-confirmed task execution and completion

### Implemented

- Append-only start/complete/skip events.
- Schedule-derived task identity, actual minutes, deviations, and mandatory reasons.
- Dependency and chronology guards.
- Optimistic versions and exact retries.
- Product completion only after every deterministic task is terminal.

### Lowest-layer task terminality

**Lowest-layer task terminality** is implemented in the exported `transition_schedule` authority.

- Direct low-level completion before terminal task evidence returns `schedule_tasks_not_terminal` with sorted remaining IDs.
- Exact retry, contradictory key reuse, stale versions, missing resources, and invalid transitions retain precedence.
- The public authority facade owns the proof and delegates mutation/commit to the preserved implementation.
- Static validation forbids product modules from importing the preserved implementation directly.
- A real PostgreSQL final-task-versus-schedule-completion race proves completion cannot commit ahead of the final task event.

### Task-execution eligibility

**Task-execution eligibility** returns `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement` before frontend mutation. A replaced source remains readable but cannot receive task events or completion. Exact proposal, acceptance, and replacement identities are exposed; backend mutation guards remain authoritative.

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
- PostgreSQL repeats viewer authorization inside the exact read-only evidence snapshot, closing the request-session/snapshot-session membership gap.
- The authenticated user ID is server-derived; the client cannot choose it.
- The operator CLI remains a separate privileged path, writes atomically, and does not substitute for HTTP authorization.
- The browser requires explicit generation, clears stale evidence after scope changes, displays server hash/isolation/counts/non-claims, downloads the complete response under a hash-addressed filename, restores focus to generated evidence, revokes object URLs, and uses no browser storage or mutation method.
- SQLite/API regressions prove complete evidence chains, owner success, nonmember `404`, operator-path separation, and no export-created rows.
- A real PostgreSQL concurrent-acceptance race proves an existing export retains the pre-acceptance snapshot while a fresh export sees the accepted replacement and a different evidence hash.

### Remaining

Signed/encrypted packages, configurable redaction, retention policy, secure object storage, support-case linkage, download audit events, size/pagination/streaming limits, and production load evidence.

## Database transient failures and exact recovery

### Implemented

**Database transient failures and exact recovery** include:

- SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return sanitized HTTP `503` responses with `database_transaction_retry_required`, `Retry-After: 1`, and same-idempotency-key guidance.
- PostgreSQL connection exceptions (`08xxx`) and invalidated connections return `database_commit_outcome_unknown`; the server does not claim whether the transaction committed.
- No automatic retry occurs in the exception handler.
- Real **statement-timeout evidence** forces SQLSTATE `57014`, rolls back, and proves a fresh exact retry creates one accepted draft.
- Real **deadlock evidence** creates an actual row-lock/advisory-lock cycle, requires one `40P01` victim, and proves exact retry converges to one acceptance and replacement.
- Lost-response evidence discards committed responses for acceptance, invalidation, and completion, then proves same-key retries return original results without duplicate rows/events.
- Real **post-commit connection-loss evidence** terminates the service PostgreSQL backend with `pg_terminate_backend()` after guarded acceptance commits but before the first refresh/response. The observed failure is classified as `database_commit_outcome_unknown`; independent reads prove one committed acceptance/replacement/event chain, and a fresh same-key retry returns it without duplication.

### Remaining

Connection loss while the COMMIT acknowledgement itself is in flight, PostgreSQL failover, pool invalidation under load, repeated serialization failures, bounded client retry policy, and SQLSTATE/retry/ambiguous-outcome/pool/lock-wait metrics and alerts.

## Provenance and coverage

### Implemented

Preparation operations coverage and derivation coverage expose explicit denominators for calendars, replayability, occurrence/request provenance, lifecycle states, task histories, original/repair methods, acceptance linkage, malformed histories, and incomplete chains. Support export captures one schedule’s current evidence chain in one canonical snapshot.

### Remaining

Alerting/SLOs, household-level signed evidence bundles, and support dashboards.

## Frontend

### Implemented

Protected plan review, occurrence confirmation, profiles/calendars, schedule persistence/approval, advisory repair, repair proposals, owner invalidation administration, accepted-draft review, schedule derivation, provenance coverage, task execution with proactive eligibility gating, and explicit support-evidence generation/download. Typed clients and focused Vitest/static contracts exist for repair, acceptance, invalidation, derivation, eligibility, and support export.

### Remaining

Authenticated PostgreSQL-backed Playwright, axe, keyboard/reflow/contrast evidence across all workflows, signed/redacted support download verification, and full generated-client parity.

## PostgreSQL concurrency evidence

### Configured

Real PostgreSQL-only fixtures cover:

- duplicate/competing acceptance and source-version uniqueness;
- acceptance versus rejection and invalidation;
- rejection versus invalidation;
- acceptance versus source task start;
- source-plan cancellation versus acceptance and repaired owner approval;
- calendar supersession versus acceptance and repaired owner approval;
- final task completion versus schedule completion;
- repeatable-read support export versus concurrent acceptance;
- duplicate/competing repaired owner approval;
- discarded-response exact retries;
- post-commit backend termination and same-key recovery;
- statement timeout and genuine deadlock recovery;
- populated `0017 → 0018` migration rehearsal;
- exact migration/dialect assertions and retained JUnit/JSON artifacts.

### Evidence status

The exact latest hosted executions and retained artifacts have not been observed in this context. Configured tests are not reported green until inspected.

## Governed research platform

### Implemented

Explicit task/dataset/model/experiment/feature contracts and offline retrieval, ranking, forecasting, uncertainty, planning, repair, inventory replay, and closed-loop baselines.

### Gated

Vision/multimodal nutrition, constrained generation, graph learning, causal/off-policy promotion, continual/federated personalization, privacy-sensitive learning, sustainability claims, and autonomous appliance/procurement control.

## Non-claims

NutriFlavorOS does not establish clinical validity, allergy or medication safety, food safety, contamination state, temperature compliance, actual task performance, human presence, appliance condition, global repair optimality, commit-acknowledgement-in-flight recovery, failover recovery, signed/export-retention guarantees, or current hosted green-build status.
