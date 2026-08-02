# Household Meal-Plan Review Lifecycle

NutriFlavorOS separates deterministic household-plan generation from human approval. A generated plan is persisted as a **draft** and cannot drive approved-plan preparation until the household owner explicitly approves its exact optimistic version.

This lifecycle is a planning and provenance control. It is not clinical validation, allergy verification, observed consumption, inventory certainty, or food-safety certification.

## Current release boundary

- Database migration head: `20260802_0014`.
- Plan-lifecycle migration: `20260802_0013`.
- API version: `0.12.1`.
- OpenAPI release contract: `2026-08-02.6`.
- Household-plan TypeScript binding contract: `2026-08-02.4`.

Migration `20260802_0013` adds optimistic lifecycle fields to `meal_plans` and creates append-only `household_plan_events`. Migration `20260802_0014` adds task execution evidence downstream without rewriting plan history.

## Persisted plan state

Each household plan retains:

- integer plan ID and household/user identity;
- immutable plan schema/document;
- `draft`, `approved`, or `cancelled` status;
- optimistic integer version;
- approver and UTC approval time;
- UTC cancellation time and reason;
- creation and update times.

Generated plans begin at `draft`, version `1`. Generation, persistence, shopping reconciliation, or reservation creation is not approval.

## Allowed transitions and roles

- `draft → approved`: owner only.
- `draft → cancelled`: editor or owner.
- `approved → cancelled`: editor or owner.
- `cancelled`: terminal.

Viewer/editor/owner may read plans and events. Unauthorized and cross-household access returns `404`.

Every transition requires:

- exact expected version;
- nonblank human reason;
- idempotency key;
- optional metadata.

An exact retry returns the existing result. Reusing a key with different content fails. A stale expected version fails with an explicit conflict.

## Append-only plan events

Approval and cancellation append events containing:

- plan and household IDs;
- event type;
- actor;
- prior and resulting status;
- reason and metadata;
- idempotency key and canonical request fingerprint;
- timestamp.

The immutable plan document is not rewritten to embed transition history.

## Cancellation side effects

Cancelling a plan atomically:

1. increments the plan version and makes it terminal;
2. releases active inventory reservations linked to the plan;
3. invalidates every linked preparation schedule still in `draft` or `approved`;
4. appends plan and schedule transition evidence;
5. preserves historical plans, reservations, schedules, occurrences, requests, responses, task events, and lifecycle events.

Completed, already cancelled, and already invalidated schedules are not rewritten.

## Planned serving semantics

For a stored plan day and meal slot, `day.portions[meal_slot]` is the planned **serving count**, not a multiplier.

Approved-plan occurrence candidates expose:

- source recipe yield;
- planned serving count;
- descriptive batch scale = planned servings ÷ source recipe yield.

Missing or unsupported serving counts fail closed.

## Approved-plan occurrence workflow

Candidate read:

`GET /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/candidates`

Explicit confirmation:

`POST /api/v1/households/{household_id}/plans/{plan_id}/preparation-occurrences/confirm`

The server requires an exact approved plan version, derives deterministic occurrence IDs from day and exact meal-slot text, never infers deadlines from slot names, and requires an include/exclude decision for every candidate.

Included occurrences require confirmed servings, explicit horizon-relative finish minute, priority, occurrence-set version, and duration policy. Active reviewed preparation-profile identity and serving-range compatibility are rechecked while the plan row is locked.

The response is a canonical non-persisted occurrence document plus exact profile-version map. It does not create or approve a schedule.

## Source-plan membership proof

Compilation and source-plan-linked persistence derive the exact candidate map from the approved plan. Every submitted occurrence must match:

- an occurrence ID produced from that plan's day and exact meal slot;
- the exact recipe stored for that meal.

Injected occurrence IDs and recipe substitutions fail closed. Confirmed servings may differ from the planned serving count only through explicit human confirmation and must remain within reviewed profile bounds.

## Downstream preparation and execution

The approved-plan preparation path remains staged and non-automatic:

1. approve plan;
2. confirm occurrences;
3. explicitly create one-time occurrence handoff;
4. select active reviewed calendar;
5. compile deterministic schedule;
6. explicitly stage operations handoff;
7. explicitly persist draft schedule;
8. owner approves after replay;
9. editor/owner records explicit task execution events;
10. schedule completion is allowed only after every deterministic task is completed or skipped.

Plan approval does not certify task execution, nutrition quality, equipment condition, temperature, contamination, or food safety.

## Deliberate limitations

- Confirmed occurrence documents become durable when incorporated into a persisted schedule; there is not yet a separate standalone occurrence-record table.
- Low-level legacy schedule completion callers still need migration to the task-terminal guard.
- Structured final persistence review, authenticated browser E2E, minimal-change repair, and joint optimization remain incomplete.
- Hosted workflows must be inspected before the current commit is described as green.
