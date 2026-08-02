# NutriFlavorOS Audit Continuation — Approved-Plan Preparation

**Continuation date:** 2026-08-02  
**Applies after:** the original exhaustive audit, provenance-coverage continuation, and structured-calendar continuation.  
**Release boundary:** migration `20260802_0013`, API `0.11.0`, OpenAPI and household-plan frontend contract `2026-08-02.5`.

This continuation supersedes earlier audit entries that listed persisted-plan lifecycle, approved-plan occurrence generation, serving/deadline confirmation, and the approved-plan-to-reviewed-pipeline bridge as incomplete.

## Completed scope

### Persisted plan lifecycle

1. Added explicit draft, approved, and cancelled states.
2. Added optimistic versions and actor/timestamp/reason provenance.
3. Added append-only approval and cancellation events.
4. Added owner-only approval and editor/owner cancellation.
5. Added idempotent identical retry and contradictory-reuse rejection.
6. Added cancellation cleanup for active pantry reservations.
7. Added cancellation invalidation for dependent draft and approved preparation schedules.
8. Added a protected plan-review workspace and event history.
9. Loaded the additive ORM mapping during backend package initialization to eliminate process import-order drift.

### Approved-plan occurrences

1. Added deterministic candidate derivation from exact plan days and meal slots.
2. Corrected serving semantics: stored portions are serving counts, not multipliers.
3. Added separate descriptive recipe batch scale.
4. Rejected missing stored serving counts.
5. Refused deadline inference from meal-slot names.
6. Required explicit include/exclude decision for every planned meal.
7. Required servings, finish minute, and priority for every included occurrence.
8. Rechecked active reviewed preparation-profile availability and serving range.
9. Returned a canonical non-persisted occurrence document and exact profile map.
10. Serialized confirmation with plan cancellation using a plan-row lock.
11. Added viewer read, editor/owner confirm, and outsider non-disclosure tests.

### Source-plan linkage

1. Added server proof that every submitted occurrence ID belongs to the approved plan.
2. Added exact occurrence-to-recipe comparison.
3. Rejected injected occurrence IDs and recipe substitutions.
4. Applied this validation during approved-plan compilation.
5. Applied the same validation before direct operations schedule persistence when a source plan is supplied.
6. Retained independent plan status/version rechecks inside the schedule mutation and approval integrity paths.

### One-time occurrence handoff

1. Added `approved-plan-occurrence-handoff-v1`.
2. Bound it to household and exact source-plan version.
3. Retained the canonical occurrence document and profile map.
4. Added a 30-minute expiry and one-time consumption.
5. Rejected malformed quantities, duplicate IDs, profile-map drift, invalid profile identities, household mismatch, future timestamps, and expiry.
6. Required a separate explicit browser action after confirmation.
7. Invalidated confirmed output after any occurrence review edit.

### Server-authoritative preparation compilation

1. Added strict compile request and response contracts.
2. Added editor/owner compile endpoint.
3. Rechecked exact approved plan under row lock.
4. Rechecked occurrence-to-plan linkage.
5. Required the active reviewed resource calendar.
6. Rechecked exact preparation profile ID/version/hash/recipe/status/active state.
7. Rechecked confirmed serving ranges.
8. Strictly validated reviewed task templates.
9. Namespaced task IDs by occurrence and preserved dependency semantics.
10. Applied explicit conservative-maximum or optimistic-minimum duration policy.
11. Reconstructed resources exclusively from the immutable calendar.
12. Returned a deterministic complete or partial schedule without persistence.
13. Kept unscheduled work explicit and blocked partial operations handoff.
14. Added service and authenticated API tests for exact, stale, drifted, unauthorized, partial, and complete states.

### Compile-to-operations bridge

1. Added a typed bridge to `preparation-operations-handoff-v2`.
2. Required complete execution, zero unscheduled work, non-empty tasks, and one scheduled result per compiled task.
3. Preserved exact calendar, plan, occurrence, profile, request, and response provenance.
4. Required a separate explicit browser action.
5. Added a protected approved-plan preparation workspace.
6. Added tests for one-time consumption, no automatic compilation, exact payloads, input invalidation, viewer restrictions, partial blocking, and explicit operations staging.

## Important defects found during implementation

### Planned servings were initially over-counted

The first derivation interpreted the stored plan portion as a multiplier and multiplied it by recipe yield. Repository inspection showed the planner already stores a serving count. The implementation and tests were corrected so:

- `planned_servings = day.portions[meal_slot]`;
- `recipe_batch_scale = planned_servings / source_recipe_servings`.

### Confirmation could race cancellation

The initial confirmation rechecked plan status but did not hold the plan lock throughout document creation. It now holds the row lock until confirmation returns.

### Compilation trusted the plan ID more than the occurrence content

The initial compiler checked plan status/version but did not prove every occurrence belonged to the plan. It now derives the exact candidate map and rejects injected occurrence IDs and recipe substitutions.

### Lifecycle ORM mapping depended on import order

The additive meal-plan mapping could be absent in processes that imported base metadata without first importing the lifecycle service. Backend package initialization now loads the mapping consistently.

### Fixed-time handoff tests could fail as the wall clock advanced

The expiry tests now generate a current timestamp and pass an explicit validation clock for deterministic expiry assertions.

## Current preparation workflow completion matrix

### Implemented

- reviewed preparation evidence;
- deterministic and exact-small-instance scheduling;
- persisted reviewed resource calendars;
- structured calendar builder;
- persisted plan lifecycle;
- exact approved-plan candidate derivation;
- explicit occurrence confirmation;
- one-time occurrence handoff;
- server-authoritative plan/profile/calendar compilation;
- explicit partial schedule diagnostics;
- complete-result operations handoff;
- occurrence-bound schedule persistence and approval replay;
- lifecycle events and provenance coverage.

### Remaining

- authenticated Playwright/PostgreSQL journey covering the entire chain;
- automated axe, keyboard-only, screen-reader, and visual-regression evidence;
- standalone immutable persistence for confirmed occurrence documents before scheduling, if product requirements justify it;
- per-task start, complete, skip, timer, reminder, and deviation events;
- minimal-change repair after pantry, plan, profile, or calendar changes;
- joint meal-selection and preparation optimization;
- larger generated DAG and compile-to-persistence property suites;
- hosted workflow observation and retained-report inspection;
- removal of fully superseded remote branch references when branch deletion becomes available.

## Verification boundary

All implementation was committed directly to `main`. No feature branch or pull request was created. The repository contains committed unit, API, frontend, migration, and concurrency tests, but the latest exact hosted workflow result was not available in the current execution environment. This continuation therefore records implementation and configured verification, not an unobserved green-build claim.
