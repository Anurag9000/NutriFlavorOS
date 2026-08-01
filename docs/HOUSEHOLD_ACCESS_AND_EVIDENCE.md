# Household Access, Reservations, and Evidence

## Household roles

- **Owner:** manage household invitations, roles, unlinked members, household
  planning, reservations, and household inventory.
- **Editor:** mutate pantry lots, leftovers, plans, and reservation workflow
  state.
- **Viewer:** read authorized household state only.

Household roles do **not** authorize mutation of global conversion,
storage-policy, or preparation evidence. Global evidence registration,
review, rejection, deactivation, and supersession remain offline controlled
operations with separate reviewer and operator identities.

Unauthorized household access returns `404` to avoid disclosing household
existence. Ownership transfer is intentionally absent until a separately
reviewed workflow handles recovery, outstanding invitations, reservations, and
audit history.

## Invitations

Invitation secrets are generated once, returned once, stored only as SHA-256
hashes, bound to the invited email, and expire. Repeated acceptance by the same
eligible account is retry-safe. Creating a replacement invitation revokes
earlier active invitations for the same household and email.

## Household targets

Every active member contributes one target source:

1. a complete linked-user profile;
2. explicit member target overrides;
3. for an unlinked planning-only member, the declared serving multiplier
   applied to the owner's explicit complete profile.

A linked account with an incomplete profile and no explicit member targets
fails planning instead of inheriting fabricated physiology.

## Stock reservations

Reservations allocate expiry-ordered lots and subtract other active
reservations from availability. They do not mutate pantry quantities until an
explicit commit. Release, expiration, and commit are versioned states. Commit
locks the lot, validates the reserved unit and quantity, updates inventory, and
writes an append-only event.

## Immutable ingredient conversions

Automatic cross-unit conversion requires an exact active reviewed immutable
record for:

- canonical ingredient;
- source unit;
- target unit.

Each record retains an immutable record version, multiplier interval, source
name/URL/version, evidence status, reviewer, UTC review time, content hash,
supersession link, and active state. Identical same-version registration is
idempotent; contradictory reuse fails. A new active reviewed version
supersedes the previous active review.

FoodData Central portion gram weights may be imported only for that exact FDC
food and measure label. An external import remains unverified until reviewed
and promoted into immutable history. Generic densities, package sizes, and
cross-food conversions are never inferred.

The reviewed-conversion API returns the exact evidence ID, record version, and
SHA-256 hash used for the result.

## Immutable storage policies

Every storage-policy version retains:

- policy key and immutable policy version;
- food category and storage state;
- duration interval and temperature assumption;
- source name, URL, and source version;
- evidence status, reviewer, and UTC review time;
- safety scope and limitations;
- content hash, supersession link, and active state.

One active reviewed version is permitted per policy key. Built-in reviewed
policies seed as version `official-2026-07-31`. Legacy records are migrated
conservatively; unreviewed or ambiguous evidence remains preserved but cannot
be used automatically.

When a new leftover selects a policy:

1. the service resolves one active reviewed immutable version;
2. storage state must match refrigerated or frozen state;
3. an explicit expiry cannot exceed the reviewed upper bound;
4. non-quality guidance may derive a conservative expiry when none is supplied;
5. quality guidance never becomes a safety-expiry timestamp;
6. the leftover, exact policy-version link, and event provenance are committed
   atomically.

The inventory event retains policy ID, policy version, and content hash. Later
supersession of the active policy does not rewrite the historical leftover
link.

Policies are conditional guidance under their stated assumptions, not safety
guarantees. Unknown foods receive no fabricated expiry, and NutriFlavorOS does
not autonomously declare food safe to eat.

## Evidence concurrency and authorization

PostgreSQL transaction advisory locks serialize immutable evidence natural
keys, including first-version races where no row exists to lock. Concurrency
probes cover identical retries, contradictory content, and concurrent
successor versions while enforcing one active reviewed record.

Authenticated users may read immutable history and apply an already reviewed
exact conversion. A household viewer may read policy provenance only for a
leftover belonging to an accessible household. Cross-household and outsider
requests return `404`.
