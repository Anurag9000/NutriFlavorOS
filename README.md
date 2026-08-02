# NutriFlavorOS

NutriFlavorOS is an **experimental household food-planning, transactional inventory, human-reviewed plan and preparation-operations, immutable-evidence, and governed research platform**.

> **Safety boundary:** NutriFlavorOS is not clinically validated, is not a medical device, does not verify allergies or medication interactions, does not declare food safe, does not infer human presence or task performance, and does not control appliances. High-risk capabilities remain gated until their data, validation, review, approval, rollback, and monitoring requirements are complete.

## Current synchronized release boundary

Development is performed through coherent commits directly to `main`. Code, tests, migrations, OpenAPI, frontend clients, CI, specifications, and status documentation must move together.

- API: `0.15.1`
- Alembic head: `20260802_0018`
- OpenAPI contract: `2026-08-02.11`
- Food-evidence frontend binding contract: `2026-08-01.2`
- Preparation-operations frontend binding contract: `2026-08-02.4`
- Household-plan frontend binding contract: `2026-08-02.4`
- Governed research catalog: `2026-08-01.3`

A committed implementation, configured workflow, passing synthetic fixture, catalog row, or importable model is not by itself an executed green-build, quality, clinical, food-safety, or deployment-readiness claim.

## Product platform

### Identity and household access

- Argon2 passwords and signed JWTs.
- Startup refusal for missing or weak signing secrets.
- Explicit profile-completion state; signup does not fabricate physiology or nutrition targets.
- Owner, editor, and viewer household roles with `404` non-disclosure.
- Hashed, expiring, email-bound, single-use invitations.

### Transactional household food state

- Versioned pantry lots with quantity intervals, units, provenance, expiry/open times, and optimistic concurrency.
- Append-only inventory and leftover events.
- FEFO allocation, expired-stock exclusion, reservations, overbooking prevention, shopping reconciliation, and batch grouping.
- Full-request idempotency fingerprints and PostgreSQL race probes.

### Deterministic meal planning

- Hard allergy and dietary filtering before optimization.
- Household target aggregation.
- Nutrition, taste, cost, cuisine, diversity, repetition, and pantry objectives.
- Persisted plan documents, serving counts, warnings, diagnostics, shopping requirements, and optional reservations.
- Pareto, optional CP-SAT/MILP, robust-scenario, and exact small-instance comparators.

## Household plan lifecycle

Generated household plans begin as `draft`. Owner approval, editor/owner cancellation, optimistic versions, exact idempotency, append-only events, reservation release, and dependent preparation-schedule invalidation are separate transactional actions.

Preparation schedule creation accepts a source plan only when the exact plan ID/version belongs to the household and remains `approved`. Generation or persistence alone is never approval.

## Immutable reviewed evidence

Immutable version histories exist for ingredient conversions, storage policies, and recipe preparation profiles. Reviewed records retain natural/version identity, source, reviewer, UTC review time, SHA-256 content hash, supersession, evidence state, and active status. Historical exact versions remain readable after withdrawal.

## Deterministic preparation scheduling

The scheduler accepts only explicit resources, capacities, non-overlapping availability windows, durations, deadlines, priorities, dependencies, and provenance.

- Empty or contradictory calendar forms fail closed.
- A task must fit inside one continuous availability window for every demanded resource.
- Tasks cannot bridge unavailable gaps.
- Heuristic and bounded exact comparators share capacity, dependency, deadline, and window semantics.
- Structured infeasibility, utilization, peak use, critical path, and replay diagnostics are retained.

## Deterministic preparation repair

Repair computation compares a complete previous deterministic schedule with a revised strict request.

- `greedy_min_change` preserves prior placements first.
- `bounded_exact_min_change` provides a small-instance comparator and reports truncation before deterministic fallback.
- Immutable tasks are pinned exactly and require compatible operational signatures and predecessor closure.
- Every candidate is revalidated against revised dependencies, horizons, deadlines, multi-window availability, and cumulative capacity.
- Results partition preserved, moved, added, removed, and unresolved tasks and retain canonical hashes.
- Advisory results always enforce `requires_human_acceptance=true`, `accepted=false`, and `persistence_performed=false`.

Advisory repair never persists, approves, executes, completes, observes, or declares safety.

## Immutable repair proposals and accepted drafts

Proposal creation persists review evidence only. The server recomputes the complete repair and binds it to exact source schedule/version/hash, source request, target reviewed calendar, occurrence/profile provenance, repair request/result, revised request, and repaired response.

The explicit lifecycle is:

1. advisory computation remains non-persistent;
2. immutable proposal creation remains non-persistent;
3. an editor or owner acknowledges every moved, added, removed, or unresolved task and accepts the proposal;
4. acceptance creates exactly one **new draft** and never mutates the source schedule;
5. an owner separately approves that draft after locked cross-record validation and method-aware replay;
6. task execution and guarded completion remain later, separate actions.

### One accepted replacement per source schedule version

Migration `20260802_0018` enforces one accepted replacement for each `(source_schedule_id, source_schedule_version)`.

- Multiple advisory proposals may be reviewed for the same source version.
- Exactly one proposal may create the accepted replacement draft.
- Exact retries are idempotent.
- Competing acceptance keys or proposals fail closed and expose the winning proposal, acceptance, and replacement schedule identities.
- Migration preflight refuses to add the invariant if conflicting historical acceptance rows exist.

## Method-aware replay and approval

Original drafts replay with `deterministic_dependency_aware_resource_scheduler_v2`. Repaired drafts replay with `deterministic_minimal_change_preparation_repair_v1`.

Repair-derived owner approval requires:

- exact proposal and acceptance identity;
- exact source schedule/version/hash and request hash;
- exact target reviewed calendar hash;
- exact repair request/result/revised-request/repaired-response hashes;
- exact changed-task acknowledgement set;
- exact created-draft identity and derivation method;
- unchanged approved source plan and occurrence/profile provenance;
- no source execution history;
- deterministic method-aware replay matching the stored repaired response and combined schedule hash.

No acceptance implies approval, and no approval implies execution.

## Schedule derivation evidence

Viewer-authorized derivation endpoints expose whether a persisted schedule came from the original scheduler or an accepted repair:

- `GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/derivation`
- `GET /api/v1/households/{household_id}/preparation-operations/schedule-derivation-coverage`

**Schedule derivation evidence** cross-checks proposal, acceptance, source, target calendar, derivation method, hashes, acknowledgement set, timestamps, and actor. Contradictory or incomplete chains fail closed or reduce coverage with explicit warnings.

The protected frontend inspector shows household coverage denominators, original-versus-repair counts, incomplete chains, exact identities, and hashes without creating lifecycle mutations.

## User-confirmed task execution

Task identity and planned timing come only from an approved persisted schedule. A client cannot invent executable tasks.

- Viewer-authorized state and append-only history.
- Editor/owner `started`, `completed`, and `skipped` confirmations.
- Horizon-relative actual minutes and planned-versus-actual deviations.
- Mandatory reasons for skips and nonzero timing deviations.
- Optimistic schedule-version increments and exact idempotent retries.
- Dependency blocking until prerequisites are terminal.
- Schedule completion only after every deterministic task is explicitly completed or skipped.

Nothing starts, completes, or skips automatically. Task events are user-entered claims, not sensor observations or safety evidence.

### Task-execution eligibility

Before the frontend enables any task or schedule-completion control, it reads:

`GET /api/v1/households/{household_id}/preparation-operations/schedules/{schedule_id}/task-execution-eligibility`

**Task-execution eligibility** classifies the selected schedule as:

- `eligible`;
- `schedule_not_approved`;
- `source_schedule_has_accepted_replacement`.

A source schedule with an accepted replacement remains readable historical evidence but cannot receive new task events or completion. The response exposes the exact proposal, acceptance, and replacement schedule identities. The protected execution workspace displays that evidence and disables every mutation before submission. The separately owner-approved replacement can become eligible in its own right.

## Frontend

Protected routes include plan review, occurrence confirmation, preparation profiles, calendars, schedule persistence and approval, advisory repair, immutable repair proposals, accepted-draft review, schedule derivation inspection, provenance/execution coverage, and user-confirmed task execution.

Typed frontend clients are contract-tested. The execution UI does not use local or session storage to bypass server authority.

## Governed research platform

Catalog `2026-08-01.3` currently defines:

- **37 task contracts**;
- **30 dataset families**;
- **75 model or algorithm families**;
- **29 experiment contracts**;
- **39 feature contracts**.

Executable offline families include retrieval/ranking baselines, temporal ranking evaluation, dense and intermittent-demand forecasting, uncertainty baselines, Pareto/CP-SAT/MILP/robust planning, exact preparation comparison, minimal-change repair, FEFO replay, and forecast-to-inventory evaluation. Catalog registration does not imply promotion or readiness.

## Validation matrix

Configured direct-`main` workflows cover:

- dependency, compile, backend, repository, Alembic, OpenAPI, frontend-binding, and static-contract checks;
- fresh SQLite and PostgreSQL migrations;
- repair unit, metamorphic, exact-comparator, proposal, acceptance, approval, tamper, execution-onset, and migration tests;
- PostgreSQL duplicate/competing acceptance, rejection, source-execution, and owner-approval races;
- schedule derivation and task-execution eligibility contracts;
- frontend typecheck and focused Vitest suites;
- machine-readable benchmark and JUnit artifacts.

The latest exact hosted workflow and retained artifacts must be inspected before the current commit is described as green.

## Local setup

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows PowerShell
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

## Deliberately incomplete or blocked

- Clinical, medication, allergy-safety, food-safety, contamination, and health-outcome claims are not validated.
- No task, presence, appliance, sensor, temperature, or safety inference is implemented.
- The lowest historical schedule-transition service still retains a compatibility path; repository authority checks prohibit product callers from using it to bypass task terminality.
- Execution-aware repair after source task history begins remains future work; ordinary repair correctly abstains.
- Joint meal, inventory, reservation, shopping, leftover, and preparation repair remains future work.
- Authenticated PostgreSQL-backed Playwright and automated accessibility evidence remain incomplete.
- Vision, multimodal nutrition, graph learning, causal/off-policy promotion, continual/federated personalization, privacy-sensitive learning, sustainability claims, and autonomous appliance/procurement control remain gated research.
- The exact latest hosted workflows have not been observed green in this execution context.

## Documentation

- [Implementation Status](docs/IMPLEMENTATION_STATUS.md)
- [Engineering and Research Roadmap](docs/ROADMAP.md)
- [Preparation Repair](docs/PREPARATION_REPAIR.md)
- [Repair Proposals](docs/PREPARATION_REPAIR_PROPOSALS.md)
- [Repair Acceptance](docs/PREPARATION_REPAIR_ACCEPTANCE.md)
- [Repair Execution Boundary](docs/PREPARATION_REPAIR_EXECUTION_BOUNDARY.md)
- [Schedule Derivation Evidence](docs/PREPARATION_SCHEDULE_DERIVATION.md)
- [Preparation Operations](docs/PREPARATION_OPERATIONS.md)
- [Governed Research Platform](docs/RESEARCH_PLATFORM.md)
