# Household access, reservations, and evidence

## Roles

- **Owner:** manage invitations, roles, members, evidence imports, planning, and inventory.
- **Editor:** mutate inventory, leftovers, plans, reservations, and member-owned workflow state.
- **Viewer:** read household state only.

Unauthorized household access returns `404` to avoid disclosing household existence. Ownership transfer is intentionally absent until a separately reviewed workflow handles recovery, outstanding invitations, reservations, and audit history.

## Invitations

Invitation secrets are generated once, stored only as SHA-256 hashes, bound to the invited email, expire, and cannot be accepted twice. Creating a replacement invitation revokes earlier active invitations for the same household/email.

## Household targets

Every active member contributes one target source:

1. a complete linked-user profile;
2. explicit member target overrides;
3. for an unlinked household member only, the declared serving multiplier applied to the owner’s explicit profile.

A linked account with an incomplete profile and no member targets fails planning rather than silently inheriting fictional physiology.

## Stock reservations

Reservations allocate expiry-ordered lots and subtract other active reservations from availability. They do not mutate pantry quantities until committed. Release, expiration, and commit are versioned states. A commit locks the lot, validates the reserved unit/quantity, updates inventory, and adds an append-only event.

## Ingredient conversions

Conversions are food-specific and evidence-specific. FoodData Central portion gram weights may create a conversion for that exact FDC food and measure label. The conversion cannot be generalized to another food. Generic densities and package sizes are never inferred.

## Storage policies

Only reviewed policies with source URLs and temperature/storage-state assumptions are seeded. Policies are guidance under their stated scope, not guarantees. Unknown recipes receive no automatic expiry. Explicit selection of a matching reviewed policy may derive an expiry, with the evidence key retained on the leftover batch.
