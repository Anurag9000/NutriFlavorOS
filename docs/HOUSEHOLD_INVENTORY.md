# Household Inventory, Leftovers, and Batch Preparation

This domain is transactional and user-owned. It replaces demo grocery state with auditable household food state.

## Implemented

- A user can create and list owned households.
- Household members carry serving multipliers, allergies, restrictions, dislikes, and active status.
- Linking a different account is rejected until an accepted-invitation workflow exists.
- Pantry lots preserve canonical ingredient name, quantity interval, canonical unit, source, expiry/opened timestamps, metadata, and optimistic version.
- Purchase, consume, discard, absolute adjustment, leftover creation, and leftover consumption create append-only inventory events.
- Idempotency keys protect retried writes from duplication.
- Stale versions return `409` instead of silently overwriting concurrent changes.
- Mass, volume, count, and culinary unit families are not mixed without an explicit conversion.
- Expired lots are excluded from shopping coverage. Stock expiring within three days is identified for use-first behavior.
- Shopping reconciliation conservatively propagates uncertainty:

  `buy_min = max(0, required_min - pantry_max)`

  `buy_max = max(0, required_max - pantry_min)`

- Leftover batches require an existing recipe and, when provided, an owner-visible source plan.
- Batch-prep tasks group repeated recipes and total their planned portions.

## Deliberate limits

- The system does not invent shelf life. Expiry is supplied by a user or verified source.
- It does not convert volume to mass without a verified density.
- It does not infer package size, edible yield, or cross-contact safety.
- Member-specific calorie/micronutrient optimization and accepted household invitations remain future work.
- Pantry-aware optimization is not yet embedded inside the horizon optimizer; the current implementation reconciles stock after planning.

## API surface

- `POST/GET /api/v1/households`
- `GET /api/v1/households/{id}`
- `POST /api/v1/households/{id}/members`
- `POST/GET /api/v1/households/{id}/pantry`
- `POST /pantry/{item_id}/consume` and `/discard`
- `PUT /pantry/{item_id}`
- `GET /inventory-events`
- `POST/GET /leftovers`
- `POST /leftovers/{id}/consume`
- `GET /shopping-reconciliation`
- `GET /batch-prep`

Every household operation verifies owner access and returns `404` for unauthorized object identifiers.
