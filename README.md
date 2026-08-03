# NutriFlavorOS

NutriFlavorOS is an **experimental household food-planning, transactional inventory, human-reviewed plan and preparation-operations, immutable-evidence, and governed research platform**.

> **Safety boundary:** NutriFlavorOS is not clinically validated, is not a medical device, does not verify allergies or medication interactions, does not declare food safe, does not infer human presence or task performance, and does not control appliances. High-risk capabilities remain gated until their data, validation, review, approval, rollback, and monitoring requirements are complete.

## Current synchronized release boundary

Development is performed through coherent commits directly to `main`. Code, tests, migrations, OpenAPI, frontend clients, CI, specifications, and status documentation must move together.

- API: `0.15.4`
- Alembic head: `20260802_0018`
- OpenAPI contract: `2026-08-03.2`
- Food-evidence frontend binding contract: `2026-08-01.2`
- Preparation-operations frontend binding contract: `2026-08-02.4`
- Household-plan frontend binding contract: `2026-08-02.4`
- Governed research catalog: `2026-08-01.3`

A committed implementation, configured workflow, synthetic fixture, catalog row, or importable model is not by itself an executed green-build, quality, clinical, food-safety, or deployment-readiness claim.

## Identity and household access

- Argon2 passwords and signed JWTs.
- Startup refusal for weak signing secrets.
- Explicit profile-completion state; signup does not fabricate physiology or nutrition targets.
- Owner, editor, and viewer household roles with `404` non-disclosure.
- Hashed, expiring, email-bound, single-use invitations.

## Transactional household food state

- Versioned pantry lots and leftovers with quantity intervals, provenance, expiry/open times, and optimistic concurrency.
- Append-only inventory and leftover events.
- FEFO allocation, expired-stock exclusion, reservations, overbooking prevention, shopping reconciliation, and batch grouping.
- Exact idempotency and PostgreSQL race probes.

## Deterministic meal planning and review

- Hard dietary/allergy filtering before optimization.
- Household target aggregation and quantity-aware nutrition, taste, cost, pantry, cuisine, diversity, and repetition objectives.
- Persisted plans, servings, warnings, diagnostics, shopping requirements, and optional reservations.
- Pareto, optional CP-SAT/MILP, robust-scenario, and exact small-instance comparators.
- Draft/approved/cancelled plan lifecycle with owner approval, editor/owner cancellation, append-only events, reservation release, and dependent schedule invalidation.
- Preparation schedules accept only the exact currently approved source plan/version.

## Immutable reviewed evidence

Immutable version histories exist for ingredient conversions, storage policies, and recipe preparation profiles. Reviewed records retain natural/version identity, source, reviewer, UTC review time, content hash, supersession, evidence state, and active status. Historical exact versions remain readable after withdrawal.

## Deterministic preparation scheduling

The scheduler accepts only explicit resources, capacities, non-overlapping windows, durations, deadlines, priorities, dependencies, and provenance.

- A task must fit in one continuous containing window for every demanded resource.
- Tasks cannot bridge availability gaps.
- Heuristic and bounded exact comparators share capacity, dependency, deadline, and window semantics.
- Structured infeasibility, utilization, peak use, critical path, and replay diagnostics are retained.
- Persisted schedules bind the exact reviewed calendar, occurrence/profile provenance, request, response, and canonical combined hash.

## Deterministic preparation repair

Repair compares a complete previous deterministic schedule with a revised strict request.

- `greedy_min_change` preserves prior placements first.
- `bounded_exact_min_change` supplies a small-instance comparator and reports truncation before deterministic fallback.
- Immutable tasks require compatible operational signatures and pinned predecessor closure.
- Candidates are revalidated against revised dependencies, horizons, deadlines, multi-window availability, and cumulative capacity.
- Results partition preserved, moved, added, removed, and unresolved tasks and retain canonical hashes.
- Advisory output always enforces `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false`.

Advisory repair never persists, approves, executes, completes, observes, or declares safety.

## Immutable repair proposals

Proposal creation persists review evidence only. The server recomputes complete repair and binds it to exact source schedule/version/hash/request, target reviewed calendar, occurrence/profile provenance, repair request/result, revised request, repaired response, and changed-task acknowledgement set.

The explicit lifecycle is:

1. advisory computation remains non-persistent;
2. immutable proposal creation remains non-persistent with respect to schedules;
3. an editor or owner acknowledges every changed task and accepts the proposal;
4. acceptance creates exactly one new `draft` and never mutates the source;
5. an owner separately approves the draft after locked evidence validation and method-aware replay;
6. task execution and guarded completion remain later actions.

### One accepted replacement per source schedule version

Migration `20260802_0018` enforces **One accepted replacement per source schedule version** for `(source_schedule_id, source_schedule_version)`.

- Multiple advisory proposals may exist for one source version.
- Exactly one may create the accepted replacement draft.
- Exact retries are idempotent.
- Competing proposals/keys fail with `repair_source_already_has_accepted_replacement` and expose the winning proposal, acceptance, and replacement identities.
- Database uniqueness prevents lower-level bypass.
- A populated PostgreSQL `0017 → 0018` rehearsal creates **64 valid accepted lifecycles** through production services, verifies exact IDs/hashes/events after upgrade, checks the live constraint definition, and proves a lower-level duplicate replacement rolls back completely.

### Owner-only proposal invalidation

**Owner-only proposal invalidation** permanently withdraws a `proposed` record without accepting it or creating a schedule.

- Requires exact expected version, nonblank reason, `acknowledge_historical_only=true`, metadata, and idempotency key.
- The server recomputes observed stale reasons and appends one immutable `invalidated` event.
- The event explicitly records no acceptance, schedule persistence, approval, or execution.
- Exact retries collapse; contradictory keys, stale versions, and terminal proposals fail closed.
- Editors may create, accept, or reject proposals but cannot invalidate them.
- The protected workspace displays current/stale evidence, exact source and repair hashes, append-only history, owner-only destructive confirmation, and read-only editor/viewer behavior.
- Real PostgreSQL acceptance-versus-invalidation and rejection-versus-invalidation probes require exactly one terminal outcome.

## Method-aware replay and owner approval

Original drafts replay with `deterministic_dependency_aware_resource_scheduler_v2`. Repaired drafts replay with `deterministic_minimal_change_preparation_repair_v1`.

Repair-derived approval requires exact proposal/acceptance/draft identity, source schedule/version/hash/request, target calendar, approved source plan, occurrence/profile provenance, changed-task acknowledgements, every repair hash, absence of source execution history, and deterministic replay matching the stored repaired response and combined schedule hash.

No acceptance implies approval, and no approval implies execution.

## Schedule derivation evidence

Viewer-authorized endpoints expose whether a persisted schedule came from the original scheduler or an accepted repair:

- `GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/derivation`
- `GET /api/v1/households/{household_id}/preparation-operations/schedule-derivation-coverage`

**Schedule derivation evidence** cross-checks proposal, acceptance, source, target calendar, method, hashes, acknowledgements, timestamps, and actor. The protected inspector shows household denominators, incomplete-chain warnings, and selected-schedule identities without lifecycle mutation.

## User-confirmed task execution

Task identity and planned timing come only from an approved persisted schedule.

- Viewer-authorized state and append-only history.
- Editor/owner `started`, `completed`, and `skipped` confirmations.
- Horizon-relative actual minutes and planned-versus-actual deviations.
- Required reasons for skips and nonzero deviations.
- Dependency, chronology, optimistic-version, and idempotency guards.
- Schedule completion only after every deterministic task is explicitly completed or skipped.

Task events are user-entered claims, not observed execution or safety evidence.

### Lowest-layer task terminality

**Lowest-layer task terminality** is enforced by the exported `transition_schedule` service itself.

- A direct `COMPLETED` transition cannot bypass task evidence.
- Exact retry, contradictory idempotency-key, optimistic-version, missing-resource, and invalid-lifecycle error precedence remain unchanged.
- A valid new `approved → completed` transition reconstructs deterministic tasks and append-only execution history under the household and schedule locks.
- Nonterminal tasks produce `schedule_tasks_not_terminal` with sorted remaining IDs.
- The named completion service is only a compatibility delegate and contains no second proof or commit path.
- Static validation forbids product modules from importing the preserved compatibility implementation directly.
- A real PostgreSQL race proves schedule completion cannot commit ahead of the final task event.

### Task-execution eligibility

Before enabling any task or schedule-completion control, the frontend reads the viewer-authorized eligibility endpoint. **Task-execution eligibility** returns `eligible`, `schedule_not_approved`, or `source_schedule_has_accepted_replacement` with exact replacement-chain identities.

A replaced source remains readable but cannot receive new task events or completion. Server guards remain authoritative.

## Preparation schedule support export

The viewer-authorized **Preparation schedule support export** endpoint is:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/support-export`

It returns a strict `preparation-schedule-support-export-v1` package containing the selected schedule, lifecycle events, derivation evidence, task-execution eligibility, deterministic task state/history, every related repair proposal, acceptance evidence, and proposal event chain.

- PostgreSQL uses a dedicated `REPEATABLE READ`, `SET TRANSACTION READ ONLY` snapshot and retains `txid_current_snapshot()` as transaction evidence.
- A canonical SHA-256 binds domain evidence while excluding transaction timestamps and snapshot metadata.
- The export explicitly reports `mutation_performed=false`, `actual_execution_verified=false`, and `food_safety_verified=false`.
- The request session requires household viewer access; PostgreSQL repeats viewer authorization inside the exact evidence snapshot, and unauthorized cross-household reads preserve `404` non-disclosure.
- The authenticated user identity is server-derived; the operator CLI is a separate privileged path and writes atomically.
- A real PostgreSQL concurrent-acceptance probe proves an in-progress export retains the pre-acceptance snapshot while a fresh export sees the accepted replacement and a different evidence hash.

## Database transient failures and exact recovery

**Database transient failures and exact recovery** are sanitized and never retried invisibly.

- SQLSTATEs `40001`, `40P01`, `57014`, and `55P03` return HTTP `503`, `Retry-After: 1`, code `database_transaction_retry_required`, and direction to retry the exact request with the same idempotency key.
- PostgreSQL connection exceptions (`08xxx`) and invalidated connections return `database_commit_outcome_unknown` because commit state may be ambiguous.
- `retryable=true` means exact client retry is the prescribed action. `retry_safe=true` is limited to proven transaction aborts; connection ambiguity reports `retry_safe=false`.
- Non-retryable operational errors return a sanitized `500` without SQL, parameters, or driver details.
- `automatic_retry_performed=false` is explicit; the exception handler does not sleep, loop, replay, or commit.
- Real PostgreSQL statement-timeout evidence forces SQLSTATE `57014`, rolls back, and proves a fresh same-key acceptance creates one draft.
- A real row-lock/advisory-lock cycle forces exactly one SQLSTATE `40P01` deadlock victim; a fresh exact retry converges to one acceptance, one replacement, and one `accepted` event.
- Discarded-response recovery tests acceptance, proposal invalidation, and schedule completion from fresh sessions and proves no duplicate rows/events.
- Real post-commit connection-loss evidence terminates the service backend after commit but before response materialization, classifies the outcome as unknown, proves one committed lifecycle, and recovers through the exact same key.
- Real checked-out pool connection invalidation evidence terminates a worker before mutation, proves no mutation occurred, requires a fresh backend PID, and converges to one acceptance through exact retry.

COMMIT-acknowledgement-in-flight loss, multi-node database failover, sustained pool exhaustion/recovery, and production load remain unverified operational boundaries.

## Frontend

Protected interfaces include plan review, occurrence confirmation, preparation profiles/calendars, schedule persistence/approval, advisory repair, immutable repair proposals, owner proposal invalidation, accepted-draft review, schedule derivation, provenance coverage, user-confirmed task execution with proactive eligibility gating, and explicit support-evidence generation/download.

Typed frontend clients are contract-tested and do not use browser storage to bypass server authority.

## Governed research platform

Catalog `2026-08-01.3` defines 37 task contracts, 30 dataset families, 75 model or algorithm families, 29 experiment contracts, and 39 feature contracts.

Executable offline families include retrieval/ranking, temporal evaluation, dense/intermittent forecasting, uncertainty, Pareto/CP-SAT/MILP/robust planning, exact preparation comparison, minimal-change repair, FEFO replay, and forecast-to-inventory evaluation. Catalog registration does not imply promotion or readiness.

## Validation matrix

Configured direct-`main` workflows cover:

- dependency, compile, backend, repository, Alembic, OpenAPI, frontend-binding, and static-contract checks;
- fresh SQLite and PostgreSQL migrations;
- populated `0017 → 0018` PostgreSQL migration rehearsal with retained JSON evidence;
- repair computation, proposal creation, acceptance, source uniqueness, invalidation, approval, tamper, derivation, task execution, lowest-layer completion, and support-export tests;
- real PostgreSQL lifecycle/dependency races, final-task/schedule-completion, repeatable-read support export, discarded-response, post-commit connection loss, checked-out pool invalidation, statement-timeout, and deadlock exact-retry evidence;
- frontend typecheck and focused Vitest suites;
- machine-readable benchmark, migration, and JUnit artifacts.

The exact latest hosted workflow and retained artifacts must be inspected before the current commit is described as green.

## Deliberately incomplete or blocked

- Clinical, medication, allergy-safety, contamination, temperature, food-safety, and health-outcome claims are not validated.
- No task, presence, appliance, or sensor inference is implemented.
- Execution-aware repair after source task history begins remains future work.
- Joint meal, inventory, reservation, shopping, leftover, and preparation repair remains future work.
- Authenticated PostgreSQL-backed Playwright and automated accessibility evidence remain incomplete.
- COMMIT-acknowledgement-in-flight recovery, failover, sustained pool recovery/load, production-snapshot migration, signed support packages, and support-retention tooling remain incomplete.
- Vision, multimodal nutrition, graph learning, causal/off-policy promotion, continual/federated personalization, sustainability claims, and autonomous control remain gated research.
- The exact latest hosted workflows have not been observed green in this execution context.

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
- [Schedule Derivation Evidence](docs/PREPARATION_SCHEDULE_DERIVATION.md)
- [Preparation Schedule Support Export](docs/PREPARATION_SCHEDULE_SUPPORT_EXPORT.md)
- [Preparation Operations](docs/PREPARATION_OPERATIONS.md)
- [Governed Research Platform](docs/RESEARCH_PLATFORM.md)
