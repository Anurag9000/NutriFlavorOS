# NutriFlavorOS Audit Continuation — Household Plan Lifecycle

**Continuation date:** 2026-08-02  
**Supersedes:** audit statements that household plans lack optimistic versions, human approval, exact source-plan eligibility, or cancellation propagation.

## Defect discovered

Preparation operations attempted to validate `source_plan_version` through `DBMealPlan.version`, but the persisted meal-plan model and database schema had no such field. A source-linked schedule could therefore fail at runtime, and there was no defensible distinction between a generated plan and a human-approved plan.

## Completed correction

1. Added migration `20260802_0013`.
2. Added optimistic `version` and `draft|approved|cancelled` state to persisted meal plans.
3. Added approval actor/time and cancellation time/reason fields.
4. Added database checks for positive versions, valid states, approval pairs, and state-specific field consistency.
5. Added append-only `household_plan_events` with constrained transition pairs, reasons, idempotency, fingerprints, and indexes.
6. Added strict domain contracts for plan views, transitions, events, states, and event types.
7. Added household row/advisory locking and optimistic transition enforcement.
8. Added exact idempotent retry and contradictory-key rejection.
9. Added owner-only approval and editor/owner cancellation.
10. Added viewer-authorized list/get/event history with `404` non-disclosure.
11. Added exact approved-plan ID/version enforcement at preparation-schedule creation.
12. Added atomic reservation release when a plan is cancelled.
13. Added atomic invalidation of dependent draft and approved preparation schedules.
14. Added append-only invalidation events containing source-plan cancellation provenance.
15. Added protected `/household/plans` review workspace.
16. Added explicit human reason gating and optimistic version payloads.
17. Added exact approved source-plan identity guidance.
18. Added frontend, service, API, and PostgreSQL race tests.
19. Added OpenAPI and TypeScript binding contract `2026-08-02.3`.
20. Bumped API to `0.9.0` and migration head to `20260802_0013`.
21. Repaired runtime schema verification so it imports the canonical reviewed head rather than carrying a stale hard-coded `0011` value.

## Cancellation invariant

Cancelling a plan now performs one transaction that:

- changes plan state and version;
- releases active reservations;
- invalidates dependent draft/approved schedules;
- appends plan and schedule events;
- records affected-row counts in event metadata.

If schedule creation races cancellation, the shared household lock and exact plan-version recheck ensure that the schedule is rejected as stale or is committed first and then invalidated.

## Remaining next slice

Human plan approval is now a real prerequisite. The next preparation workflow work is:

1. select an exact approved plan;
2. derive candidate meal occurrences from its immutable stored document;
3. require household confirmation of servings and finish deadlines;
4. expose missing reviewed preparation profiles;
5. compile and review tasks against the active reviewed calendar;
6. persist only after explicit confirmation and server replay.

The raw schedule-bundle JSON path, per-task execution events, authenticated browser E2E, full accessibility automation, and joint minimal-change repair remain incomplete.
