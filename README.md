# NutriFlavorOS

NutriFlavorOS is an **experimental household food-planning, transactional inventory, human-reviewed preparation-operations, immutable-evidence, and governed research platform**.

> **Safety boundary:** NutriFlavorOS is not clinically validated, is not a medical device, does not verify allergy or medication safety, does not declare food safe, does not infer human presence or task performance, and does not control appliances.

## Current synchronized release boundary

Development uses coherent commits directly to `main`. Code, tests, migrations, OpenAPI, frontend clients, CI, specifications, and status documentation move together.

- API: `0.15.4`
- Alembic head: `20260802_0018`
- OpenAPI contract: `2026-08-03.2`
- Food-evidence frontend binding: `2026-08-01.2`
- Preparation-operations frontend binding: `2026-08-02.4`
- Household-plan frontend binding: `2026-08-02.4`
- Governed research catalog: `2026-08-01.3`

Committed implementation and configured workflows are not automatically executed green evidence.

## Core platform

- Argon2 passwords, signed JWTs, weak-secret refusal, explicit profile completion, and owner/editor/viewer household roles with `404` non-disclosure.
- Versioned pantry lots and leftovers, append-only inventory events, FEFO allocation, reservations, shopping reconciliation, optimistic versions, and exact idempotency.
- Quantity-aware deterministic meal planning, persisted plan lifecycle, owner approval, cancellation consequences, Pareto, optional CP-SAT/MILP, robust scenarios, and exact comparators.
- Immutable reviewed ingredient-conversion, storage-policy, and preparation-profile evidence with source, reviewer, version, content hash, supersession, and active state.
- Reviewed resource calendars, canonical occurrence/profile provenance, deterministic scheduling/replay, combined hashes, and persisted schedule lifecycle.

## Deterministic preparation repair

Repair compares a complete previous deterministic schedule with a revised strict request.

- `greedy_min_change` preserves compatible placements first.
- `bounded_exact_min_change` provides a small-instance comparator and deterministic fallback.
- Immutable anchors, predecessor closure, capacities, continuous windows, deadlines, dependencies, and canonical hashes are revalidated.
- Outcomes partition preserved, moved, added, removed, and unresolved tasks.
- Advisory output always reports `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false`.

Advisory repair never persists, approves, executes, completes, observes, or declares safety.

## Immutable repair lifecycle

Proposal creation persists server-recomputed review evidence only. It binds exact source schedule/version/hash/request, reviewed target calendar, source plan, occurrence/profile provenance, repair request/result, revised request, repaired response, and changed-task acknowledgement set.

1. Advisory computation remains non-persistent.
2. Proposal creation creates no schedule.
3. An editor or owner acknowledges every changed task and accepts.
4. Acceptance creates exactly one new `draft` and never mutates the source.
5. An owner separately approves after locked evidence validation and method-aware replay.
6. Task execution and schedule completion remain separate actions.

### One accepted replacement per source schedule version

Migration `20260802_0018` enforces **One accepted replacement per source schedule version**.

- Multiple advisory proposals may exist.
- Exactly one creates the accepted replacement.
- Exact retries are idempotent.
- Competing proposals return `repair_source_already_has_accepted_replacement` and the winning identities.
- Database uniqueness prevents lower-level bypass.
- A populated `0017 → 0018` rehearsal creates **64 valid accepted lifecycles**, verifies exact IDs/hashes/events after upgrade, checks the live constraint, and proves bypass rollback.

### Owner-only proposal invalidation

**Owner-only proposal invalidation** closes a `proposed` review record without accepting it or creating a schedule. It requires exact version, reason, historical-only acknowledgement, metadata, and idempotency; records server-observed stale reasons; appends immutable evidence; and leaves editors/viewers read-only.

## Method-aware approval, derivation, and execution

Original drafts replay through `deterministic_dependency_aware_resource_scheduler_v2`. Accepted repair drafts replay through `deterministic_minimal_change_preparation_repair_v1` and require exact proposal, acceptance, source, plan, calendar, provenance, acknowledgement, and hash evidence.

**Schedule derivation evidence** exposes original-versus-repair provenance through per-schedule and household coverage endpoints plus a protected inspector.

**Lowest-layer task terminality** is enforced by exported `transition_schedule`; direct completion cannot bypass explicit completed/skipped task evidence.

**Task-execution eligibility** returns `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement`. Replaced sources remain readable but cannot receive task events or completion. Server guards remain authoritative.

User-entered task events are claims, not observed execution or food-safety evidence.

## Preparation schedule support export

The viewer-authorized **Preparation schedule support export** endpoint returns one strict, hash-addressed, read-only evidence package containing schedule provenance, lifecycle events, derivation, eligibility, deterministic task history, related proposals, acceptances, and proposal events.

- PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, and `txid_current_snapshot()`.
- Viewer authorization is checked in the request session and repeated inside the exact evidence snapshot.
- The user identity is server-derived; the operator CLI is a separate privileged path.
- Canonical SHA-256 binds domain evidence and explicit non-claims.
- The browser supports explicit generation and complete JSON download without browser storage or mutation methods.
- A concurrent-acceptance PostgreSQL test proves stable historical and fresh snapshots.

## Database transient failures and exact recovery

**Database transient failures and exact recovery** distinguish prescribed recovery from proof that automatic retry is safe.

- SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return `database_transaction_retry_required`, HTTP 503, `Retry-After: 1`, and exact same-key guidance.
- Connection exceptions and invalidated connections return `database_commit_outcome_unknown`.
- `retryable=true` means the caller should repeat the exact idempotent request.
- `retry_safe=true` is reserved for proven transaction aborts.
- Connection ambiguity reports `retry_safe=false`.
- The HTTP handler always reports `automatic_retry_performed=false`.

Real PostgreSQL evidence covers statement timeout, genuine deadlock, discarded committed responses, post-commit backend termination, checked-out pool invalidation, and three genuine serializable `40001` aborts followed by a fourth exact-key attempt that creates one acceptance and replacement.

The bounded retry utility preserves one normalized idempotency key, applies finite exponential backoff, emits immutable attempt observations, raises at the exact bound, and never automatically replays `database_commit_outcome_unknown`.

## Database recovery observability

The **database recovery observability** foundation records privacy-preserving process metrics for sanitized HTTP operational errors and explicit bounded retries.

- Only bounded error codes and SQLSTATE buckets are retained.
- Immutable snapshots expose transaction-abort, outcome-unknown, invalidated-connection, scheduled-retry, successful-convergence, exhaustion, and delay counters.
- Thread-safe tests prove exact aggregation under 1,600 concurrent updates.
- SQL, parameters, exception messages, idempotency keys, household/user/proposal/schedule IDs, food data, and request payloads are never recorded.
- Process-local alert evaluation covers ambiguous outcomes, exhausted retry budgets, transaction-abort volume, and invalidated connections.
- No public metrics HTTP endpoint is exposed.

Persistent time windows, cross-replica aggregation, dashboards, paging, ownership, runbooks, and SLOs remain deployment work.

## Frontend and evidence

Protected interfaces cover plan review, occurrence confirmation, calendars, schedule persistence/approval, advisory repair, proposal lifecycle, owner invalidation, accepted-draft review, derivation coverage, execution eligibility, task execution, and support evidence export.

Typed clients and focused tests do not use browser storage to bypass server authority.

## Governed research platform

Catalog `2026-08-01.3` defines 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts. Offline executable families include retrieval/ranking, forecasting, uncertainty, robust/Pareto planning, exact comparators, minimal-change repair, FEFO replay, and closed-loop inventory evaluation. Catalog registration does not imply promotion or readiness.

## Validation matrix

Configured direct-`main` workflows cover fresh SQLite/PostgreSQL migrations, OpenAPI/release identity, backend/static contracts, frontend typecheck/Vitest, repair/proposal/acceptance/invalidation/approval/derivation/execution tests, PostgreSQL lifecycle and dependency races, support snapshot concurrency, migration rehearsal, timeout/deadlock recovery, connection termination, pool invalidation, repeated serialization retry, recovery observability, and retained benchmark/JUnit/JSON evidence.

The exact latest hosted workflows and artifacts must be inspected before the current commit is described as green.

## Deliberately incomplete

- COMMIT-acknowledgement-in-flight connection loss, multi-node failover, sustained pool exhaustion/recovery, and production-scale migration rehearsal.
- Authenticated production metrics aggregation, persistence, dashboards, paging, SLOs, and runbooks.
- Authenticated PostgreSQL-backed Playwright and complete accessibility evidence.
- Signed/encrypted/redacted support packages, retention, storage, support-case linkage, and audit events.
- Execution-aware repair and joint meal/inventory/reservation/shopping/leftover/preparation repair.
- Clinical, allergy, medication, contamination, temperature, food-safety, actual-execution, human-presence, appliance, global-optimality, and deployment-readiness claims.

## Local setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
alembic upgrade head
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

```bash
cd frontend
npm ci
npm run dev
```

PostgreSQL is recommended for concurrent or hosted deployments.

## Documentation

- [Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Preparation Repair](docs/PREPARATION_REPAIR.md)
- [Repair Proposals](docs/PREPARATION_REPAIR_PROPOSALS.md)
- [Repair Acceptance](docs/PREPARATION_REPAIR_ACCEPTANCE.md)
- [Repair Execution Boundary](docs/PREPARATION_REPAIR_EXECUTION_BOUNDARY.md)
- [Pool Invalidation Recovery](docs/PREPARATION_REPAIR_POOL_INVALIDATION.md)
- [Bounded Serialization Retry](docs/PREPARATION_REPAIR_SERIALIZATION_RETRY.md)
- [Database Recovery Observability](docs/DATABASE_RECOVERY_OBSERVABILITY.md)
- [Schedule Derivation Evidence](docs/PREPARATION_SCHEDULE_DERIVATION.md)
- [Preparation Schedule Support Export](docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md)
- [Preparation Operations](docs/PREPARATION_OPERATIONS.md)
- [Governed Research Platform](docs/RESEARCH_PLATFORM.md)
