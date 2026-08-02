# Approved-Plan Preparation Workflow

**Release boundary:** API `0.11.0`, migration head `20260802_0013`, OpenAPI and household-plan frontend contract `2026-08-02.5`.

This workflow converts an exact approved household meal-plan version into a reviewable, deterministic, occurrence-bound preparation schedule without silently inferring deadlines, trusting stale evidence, or persisting work automatically.

## End-to-end stages

1. A household plan is generated and persisted as `draft`.
2. The household owner explicitly approves one optimistic plan version.
3. Authorized users load preparation-occurrence candidates from that exact approved plan/version.
4. The household explicitly includes or excludes every planned meal.
5. Every included meal receives confirmed servings, required finish minute, and priority.
6. The server rechecks reviewed preparation-profile availability and serving-range compatibility.
7. The server returns a canonical, non-persisted occurrence document and exact profile-version map.
8. A separate explicit browser action stores a one-time, 30-minute occurrence handoff.
9. The approved-plan preparation pipeline consumes that handoff once.
10. The user selects the active reviewed household resource calendar and scheduling granularity.
11. The server rechecks plan status/version, occurrence-to-plan linkage, profile identities, serving ranges, task templates, and calendar state.
12. The deterministic scheduler returns complete or explicitly partial output without persistence.
13. Partial or unscheduled output cannot be staged for operations.
14. A separate explicit browser action creates the existing operations handoff v2.
15. The operations workspace requires another explicit persistence action.
16. Schedule persistence and later approval independently replay and revalidate the full occurrence, plan, profile, calendar, request, and response provenance.

No step automatically approves the next step.

## Household-plan lifecycle

Migration `20260802_0013` adds a durable lifecycle to persisted meal plans:

- `draft`;
- `approved`;
- `cancelled`.

It also adds optimistic `version`, approver/cancellation provenance, `updated_at`, and append-only `household_plan_events`.

Authorization:

- viewer, editor, owner: read plans and events;
- owner: approve a draft;
- editor or owner: cancel a draft or approved plan.

Cancellation releases active reservations and invalidates dependent draft or approved preparation schedules. Historical plan, reservation, schedule, and event records remain readable.

The additive lifecycle ORM mapping is loaded during backend package initialization so every API process, test, CLI, Alembic environment, and `Base.metadata` schema sees the same columns and event table independent of import order.

## Candidate generation

`GET /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/candidates`

requires `expected_plan_version` and an approved plan.

Candidate identity is deterministic from the plan day and exact meal-slot string. The response includes:

- occurrence ID;
- day and meal slot;
- recipe ID and name;
- source recipe yield;
- planned serving count;
- descriptive recipe batch scale;
- active reviewed preparation-profile identity and supported serving range when available;
- explicit missing/incompatible profile state.

### Serving semantics

`day.portions[meal_slot]` is the stored planned **serving count**. It is not multiplied by recipe yield.

`recipe_batch_scale` is separately calculated as:

`planned_servings / source_recipe_servings`

This distinction is enforced in backend, API, TypeScript, and regression tests. A stored meal without an explicit serving count fails closed.

### No deadline inference

Meal-slot names such as Breakfast, Lunch, Dinner, or Snack are never converted into timestamps. Required finish minutes must be entered explicitly against the preparation horizon.

## Explicit occurrence confirmation

`POST /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/confirm`

requires editor or owner access and:

- exact expected plan version;
- immutable occurrence-set version;
- duration policy;
- exactly one include/exclude decision for every candidate;
- confirmed servings, finish minute, and priority for every included occurrence.

The server holds the source-plan row lock while confirming so plan cancellation cannot complete between candidate derivation and the returned canonical document.

Every included occurrence must have an active reviewed preparation profile compatible with confirmed servings. Missing evidence and serving-range drift fail closed.

The response contains:

- canonical `PreparationOccurrenceSetDocument`;
- exact `profile:{id}/version:{version}/sha256:{hash}` map;
- included/excluded counts;
- explicit non-persistence warnings.

The response is not itself stored as an operational record.

## Occurrence-to-plan linkage

Compilation and direct operations persistence do not trust a plan ID alone. Every submitted occurrence must identify an occurrence ID derived from that approved plan and the exact recipe present in that plan meal.

The server rejects:

- injected occurrence IDs;
- a valid occurrence ID paired with a substituted recipe;
- stale or cancelled plan versions;
- route/document household mismatch.

Confirmed servings may differ from the original planned serving count because they are an explicit human confirmation, but they must remain within the active reviewed profile range.

## One-time occurrence handoff

The browser handoff version is `approved-plan-occurrence-handoff-v1`.

It retains:

- household ID;
- source plan ID/version;
- canonical occurrence document;
- exact profile-version map;
- creation timestamp.

Properties:

- stored in session storage only after a separate explicit action;
- expires after 30 minutes;
- consumed and removed on first pipeline load;
- household and plan-version bound;
- exact occurrence-recipe/profile-map validation;
- malformed quantities, duplicate IDs, invalid profile identities, future timestamps, and expired documents fail closed.

Editing any occurrence review field after confirmation invalidates the visible confirmed output and removes the option to open the pipeline until reconfirmed.

## Server-authoritative compilation

`POST /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/compile`

requires editor or owner access and:

- exact approved plan version;
- active reviewed resource-calendar ID;
- canonical occurrence document;
- exact profile-version map;
- explicit scheduling granularity.

Under the source-plan row lock, the service:

1. proves every occurrence ID and recipe belong to the approved source plan;
2. verifies the route and occurrence household;
3. requires the selected calendar to remain active and reviewed;
4. parses and verifies each exact profile identity;
5. rejects superseded, inactive, rejected, missing, version-drifted, hash-drifted, or recipe-mismatched profiles;
6. checks confirmed servings against reviewed ranges;
7. strictly validates stored task templates;
8. namespaces task IDs by occurrence;
9. maps template dependencies within each occurrence;
10. selects reviewed maximum or minimum duration according to the confirmed duration policy;
11. reconstructs resources exclusively from the immutable reviewed calendar;
12. builds a strict deterministic schedule request;
13. executes the deterministic dependency/resource scheduler;
14. returns complete or explicitly partial output without persistence.

Task metadata retains occurrence, recipe, servings, profile ID/version/hash, duration bounds/policy, template ID/name, active-work declaration, unattended declaration, and notes. This is the provenance later required by operations persistence.

## Partial scheduling

Compilation may return `partial_unscheduled` with machine-readable reasons such as missing resource, unavailable continuous window, insufficient capacity, blocked dependency, or deadline infeasibility.

Partial output remains visible for review but cannot be handed to operations. No task is silently dropped and no constraint is silently relaxed.

## Compile-to-operations handoff

A complete compile result can be transformed into `preparation-operations-handoff-v2` only after another explicit action.

The bridge requires:

- `partial == false`;
- zero unscheduled tasks;
- execution status `complete`;
- at least one task;
- every compiled task represented in the deterministic schedule;
- internally consistent household, plan, calendar, and occurrence provenance.

The operations bundle contains:

- calendar ID;
- exact source plan ID/version;
- canonical occurrence document;
- exact profile versions;
- full schedule request;
- full deterministic response;
- human-readable source notes;
- local occurrence hash preview.

The operations workspace still does not persist automatically. Server persistence and owner approval each repeat integrity checks.

## Frontend routes

- `/household/plans` — plan lifecycle review;
- `/household/plans/occurrences` — candidate and occurrence confirmation;
- `/preparation/pipeline/approved-plan` — active-calendar selection and deterministic compilation;
- `/preparation/operations` — persistence and lifecycle review;
- `/preparation/operations/calendars/new` — reviewed resource-calendar builder;
- `/preparation/operations/coverage` — provenance denominators.

The older `/preparation/pipeline` route remains a distinct manual reviewed-profile workflow and is not silently mixed with the approved-plan path.

## Regression coverage

Committed tests cover:

- serving-count and batch-scale semantics;
- missing stored serving counts;
- draft, stale, cancelled, and outsider plan rejection;
- explicit decision for every candidate;
- reviewed profile availability and serving-range recheck;
- candidate/recipe source-plan linkage;
- occurrence injection and recipe substitution;
- viewer/editor authorization;
- confirmation/cancellation serialization;
- handoff expiry, corruption, one-time consumption, and profile-map drift;
- no automatic compile or persistence;
- exact compile request payload;
- conservative and optimistic duration policies;
- profile identity drift;
- inactive calendar rejection;
- complete and partial deterministic schedules;
- partial operations-handoff blocking;
- compiled-output invalidation after calendar or granularity changes;
- exact operations v2 bundle construction.

## Deliberate limitations

- Confirmation does not certify nutritional correctness, allergy safety, food safety, equipment condition, or task execution.
- Required finish minutes are horizon-relative declarations, not inferred clock times.
- The workflow does not yet persist a standalone confirmed occurrence document; schedule persistence retains the canonical occurrence payload.
- There are no per-task start, complete, skip, timer, or deviation events yet.
- There is no automatic schedule repair after an infeasible compile.
- No appliance control, presence inference, sensor verification, or autonomous procurement is performed.
- Authenticated Playwright/PostgreSQL and automated accessibility journeys remain incomplete.
- The exact latest hosted workflow run must be observed before the current `main` SHA is described as green.
