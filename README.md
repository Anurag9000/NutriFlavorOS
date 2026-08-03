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

NutriFlavorOS includes household roles with `404` non-disclosure, versioned pantry and leftovers, append-only inventory events, FEFO allocation, reservations, quantity-aware deterministic meal planning, reviewed evidence, reviewed preparation calendars/profiles, deterministic scheduling and replay, canonical hashes, optimistic versions, and exact idempotency.

## Deterministic repair and immutable lifecycle

Advisory repair revalidates capacities, continuous windows, deadlines, dependencies, immutable anchors, predecessor closure, and canonical hashes. It always reports `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false`.

The immutable lifecycle separates computation, proposal creation, human acceptance, owner approval, task execution, and schedule completion. No step implies a later step.

### One accepted replacement per source schedule version

Migration `20260802_0018` enforces **One accepted replacement per source schedule version**. Multiple proposals may exist, but exactly one may create the accepted draft replacement. Competing proposals return `repair_source_already_has_accepted_replacement`; exact retries return the original identities; database uniqueness prevents lower-level bypass.

### Owner-only proposal invalidation

**Owner-only proposal invalidation** closes a `proposed` review record without creating a schedule. It requires exact version, historical-only acknowledgement, reason, metadata, and idempotency and appends immutable evidence.

## Derivation and execution authority

**Schedule derivation evidence** exposes original-versus-repair provenance through per-schedule and household coverage endpoints plus a protected inspector.

**Lowest-layer task terminality** is enforced by exported `transition_schedule`; direct completion cannot bypass explicit completed/skipped task evidence.

**Task-execution eligibility** returns `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement`. Replaced sources remain readable but cannot receive new task events or completion.

## Preparation schedule support export

The viewer-authorized **Preparation schedule support export** endpoint, operator CLI, typed GET-only client, and protected browser workspace produce one strict, hash-addressed, read-only evidence package. PostgreSQL uses `REPEATABLE READ`, `SET TRANSACTION READ ONLY`, and snapshot-internal viewer authorization. Export fields explicitly deny mutation, actual-execution verification, and food-safety verification.

## Database transient failures and exact recovery

**Database transient failures and exact recovery** distinguish prescribed recovery from proof that automatic retry is safe.

- SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return `database_transaction_retry_required`.
- Connection exceptions and invalidated connections return `database_commit_outcome_unknown` with `retry_safe=false`.
- Connection ambiguity dominates nominal abort SQLSTATEs; an invalidated `40001` is outcome-unknown, not retry-safe.
- Pool checkout exhaustion returns `database_pool_timeout`, `no_transaction_started=true`, `retry_safe=true`, `outcome_unknown=false`, and `failure_stage=connection_checkout`.
- The HTTP server always reports `automatic_retry_performed=false`.
- Explicit bounded retry preserves the exact idempotency key and never automatically replays ambiguous connection outcomes.

Real PostgreSQL evidence covers statement timeout, deadlock, lost response, **post-commit connection-loss recovery**, **checked-out pool connection recovery**, repeated serialization aborts, and controlled pool exhaustion.

The **controlled sustained pool pressure** corpus occupies a two-connection pool and runs three synchronized waves with eight callers per wave. All **24 checkout timeouts** produce zero lifecycle mutation, preserve `no_transaction_started=true`, and recover after capacity returns through the same exact idempotency key. The pool proves `checkedout() == 0` before and after recovery. This is not representative production capacity.

The **controlled application-worker recycle** boundary runs an old subprocess with a fully occupied one-connection pool. It publishes a stable worker-instance identity and live PostgreSQL backend PID, times out before transaction start with zero lifecycle mutation, receives an orderly stdin recycle request, closes its pool, and exits. The parent proves the old PostgreSQL backend disappears. A **fresh worker process** publishes a different worker-instance identity and backend PID, performs the same exact-key acceptance once, and closes without a pool leak. This is not ungraceful crash recovery or multi-node failover.

## Database recovery observability

The **database recovery observability** foundation records privacy-preserving process metrics and deterministic OpenMetrics text using bounded error-code and SQLSTATE labels.

- SQL, parameters, exception messages, idempotency keys, domain IDs, food data, and request payloads are excluded.
- **Exact classification integrity** requires code and proof flags to agree before counters change.
- Negative, boolean, nonnumeric, `NaN`, and infinite retry timing is rejected atomically; alert thresholds must be positive integers.
- Thread-safe snapshots expose retry, exhaustion, ambiguity, invalidation, pool-timeout, convergence, and delay evidence.
- Alert evaluation covers outcome unknown, retry exhaustion, transaction-abort volume, invalidated connections, and pool checkout timeout.
- Unbounded labels and malformed metric values fail closed.
- **No public metrics HTTP endpoint** is exposed.

Cross-replica aggregation, persistence, dashboards, paging, ownership, runbooks, and SLOs remain deployment work.

## Frontend, research, and validation

Protected interfaces cover plan review, occurrence confirmation, calendars, schedule persistence/approval, advisory repair, proposal lifecycle, invalidation, accepted-draft review, derivation coverage, execution eligibility, task execution, and support export.

Catalog `2026-08-01.3` defines 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts. Catalog registration does not imply readiness.

Configured direct-`main` workflows cover SQLite/PostgreSQL migrations, backend/static/OpenAPI contracts, frontend typecheck/Vitest, lifecycle races, migration rehearsal, support snapshot concurrency, timeout/deadlock recovery, connection termination, pool invalidation, serialization retry, controlled single-checkout exhaustion, controlled sustained pool pressure, controlled application-worker recycle, observability, and retained benchmark/JUnit/JSON evidence.

The exact latest hosted workflows and artifacts must be inspected before the current commit is described as green.

## Deliberately incomplete

- COMMIT-acknowledgement-in-flight loss, ungraceful crash recovery, multi-node failover, representative production capacity, and production-scale migration rehearsal.
- Authenticated production metrics aggregation and SLO operations.
- PostgreSQL-backed Playwright and complete accessibility evidence.
- Signed/encrypted/redacted support packages and retention/audit tooling.
- Execution-aware and joint meal/inventory/preparation repair.
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
- [Pool Exhaustion Recovery](docs/PREPARATION_REPAIR_POOL_EXHAUSTION.md)
- [Controlled Sustained Pool Pressure](docs/PREPARATION_REPAIR_POOL_PRESSURE.md)
- [Controlled Worker Recycle](docs/PREPARATION_REPAIR_WORKER_RECYCLE.md)
- [Bounded Serialization Retry](docs/PREPARATION_REPAIR_SERIALIZATION_RETRY.md)
- [Database Recovery Observability](docs/DATABASE_RECOVERY_OBSERVABILITY.md)
- [Schedule Derivation Evidence](docs/PREPARATION_SCHEDULE_DERIVATION.md)
- [Preparation Schedule Support Export](docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md)
- [Preparation Operations](docs/PREPARATION_OPERATIONS.md)
- [Governed Research Platform](docs/RESEARCH_PLATFORM.md)
