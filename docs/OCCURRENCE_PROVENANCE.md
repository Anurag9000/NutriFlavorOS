# Server-Verified Preparation Occurrence Provenance

Persisted preparation operations do not trust a client-supplied occurrence-set digest.
The client submits the complete strict `preparation-occurrence-set-v1` document.
The server normalizes the document, derives its SHA-256 hash, verifies household,
version, recipe, servings, priority, deadline, duration-policy, and preparation-profile
links against every compiled task, stores the document and hash, and repeats those
checks before approval.

Rows created before occurrence-document persistence remain readable but cannot be
approved until an exact matching document is supplied through the bound idempotent
creation request. Contradictory documents are rejected and historical provenance is
not silently rewritten.
