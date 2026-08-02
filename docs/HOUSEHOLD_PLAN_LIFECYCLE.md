# Household Meal-Plan Review Lifecycle

NutriFlavorOS separates deterministic household-plan generation from human approval. A generated plan is persisted as a **draft**. It cannot be used as the source of preparation occurrences until the household owner explicitly approves its exact optimistic version.

This lifecycle is a planning and provenance control. It is not clinical validation, allergy verification, observed consumption, inventory certainty, or food-safety certification.

## Migration and API boundary

- Migration head: `20260802_0013`.
- API version: `0.9.0`.
- OpenAPI release contract: `2026-08-02.3`.
- Household-plan TypeScript binding contract: `2026-08-02.3`.

Migration `20260802_0013` adds optimistic lifecycle fields to `meal_plans` and creates append-only `household_plan_events`.

## Persisted plan state

Each household plan retains:

- integer primary key;
- household and creator identity;
- immutable stored plan document and plan-schema version;
- lifecycle status;
- optimistic version;
- approver and approval time;
- cancellation time and reason;
- creation and update times.

Statuses:

- `draft` — generated and persisted, but not accepted as a preparation source;
- `approved` — exact plan version explicitly accepted by the owner;
- `cancelled` — terminal household decision that invalidates dependent operational work.

Allowed transitions:

- `draft → approved`;
- `draft → cancelled`;
- `approved → cancelled`.

Cancelled plans are terminal. Regeneration creates another plan record rather than rewriting historical content.

## Human approval

Approval requires:

- owner authorization;
- exact expected optimistic version;
- nonblank human reason;
- idempotency key;
- optional structured metadata.

The transition:

1. locks the household operation scope;
2. checks an existing event for exact idempotent retry;
3. locks the plan row;
4. validates the expected version and current state;
5. records approver and UTC approval time;
6. increments the optimistic version;
7. appends one immutable `approved` event in the same transaction.

The approved version after a new draft version `1` is normally version `2`. Preparation schedules must retain that exact ID/version pair.

Approval does **not** mean:

- all nutrition targets are medically appropriate;
- allergy or medication interactions are clinically verified;
- every ingredient is in stock;
- the household will consume the selected meals;
- a preparation profile or resource calendar exists;
- preparation is automatically scheduled or approved.

## Cancellation and dependent work

Cancelling a draft or approved plan is atomic with its operational consequences:

1. the plan becomes `cancelled` and its version increments;
2. all active stock reservations for that plan become `released` and increment their versions;
3. every dependent preparation schedule still in `draft` or `approved` becomes `invalidated`;
4. each invalidated schedule receives an append-only `invalidated` event containing the source-plan ID/version and cancellation provenance;
5. one append-only plan `cancelled` event records counts of released reservations and invalidated preparation schedules.

Completed, cancelled, or already invalidated schedules are not rewritten.

## Exact source-plan eligibility

The preparation-operations schedule creation API accepts a source plan only when:

- plan ID and version are both supplied;
- the plan belongs to the route household;
- the optimistic version matches exactly;
- the current status is `approved`.

Failure codes include:

- `source_plan_version_mismatch`;
- `source_plan_not_approved`;
- `stale_plan_version`;
- `invalid_plan_transition`;
- `plan_transition_idempotency_conflict`.

The preparation service also rechecks plan identity/version while persisting. If cancellation races creation, the shared household row lock and version change ensure that either the schedule is rejected as stale or it is committed first and then invalidated by cancellation.

## Append-only events

`household_plan_events` retains:

- plan and household IDs;
- event type;
- actor;
- previous and new state;
- normalized reason;
- metadata;
- idempotency key;
- SHA-256 request fingerprint;
- creation time.

Event constraints permit only:

- `approved: draft → approved`;
- `cancelled: draft|approved → cancelled`.

Identical retries return the current plan without adding another event. Reusing the same idempotency key with different content fails closed.

## Authorization

Authenticated APIs are under:

`/api/v1/households/{household_id}/plans`

- list/get/events: viewer, editor, or owner;
- approve: owner only;
- cancel: editor or owner.

Unauthorized and cross-household access returns `404` to avoid record disclosure.

## Frontend

The protected `/household/plans` workspace provides:

- household selection and role display;
- draft, approved, and cancelled counts;
- exact plan ID, optimistic version, schema version, meals, portions, warnings, and timestamps;
- explicit reason entry;
- owner approval;
- editor/owner cancellation;
- exact approved source-plan ID/version guidance;
- append-only transition history;
- warnings that cancellation releases reservations and invalidates dependent schedules.

The page never approves automatically after generation.

## Verification

Committed verification includes:

- service tests for optimistic versions, exact retry, contradictory key reuse, stale versions, source-plan eligibility, reservation release, and schedule invalidation;
- API tests for owner approval, viewer reads, event history, mutation non-disclosure, and outsider non-disclosure;
- frontend tests for reason gating, exact optimistic version payloads, cancellation, event history, and viewer controls;
- PostgreSQL probes for identical concurrent approval retries and competing approval/cancellation;
- generated OpenAPI and TypeScript binding gates;
- fresh SQLite and PostgreSQL migration jobs.

Configured or committed validation is not represented as executed green evidence until the exact hosted workflow run is observed.

## Remaining work

- derive candidate occurrences from an exact approved plan version;
- require household confirmation of servings and finish deadlines;
- expose reviewed preparation-profile availability per planned recipe;
- build and review the immutable occurrence document;
- replace raw schedule-bundle JSON with a structured schedule review surface;
- add authenticated Playwright/PostgreSQL and accessibility coverage;
- add explicit ownership transfer and plan archive/export policy;
- add minimal-change repair after plan, pantry, evidence, or calendar changes.
