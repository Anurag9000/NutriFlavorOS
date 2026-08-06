"""Stable identity contract for meal occurrences derived from approved plans.

Occurrence identifiers are persisted and passed across confirmation, compilation,
schedule persistence, execution, and repair boundaries. The algorithm therefore
belongs to the domain contract rather than to one service implementation.
"""

from __future__ import annotations

import hashlib
import re


MAX_NORMALIZED_MEAL_SLOT_LENGTH = 80
MEAL_SLOT_DIGEST_LENGTH = 16


def approved_plan_occurrence_id(day: int, meal_slot: str) -> str:
    """Return the stable identifier for one approved-plan meal occurrence.

    The readable component is normalized and bounded. A digest of the exact meal
    slot preserves identity when distinct source labels normalize to the same
    readable component. Callers remain responsible for validating the plan day
    and for rejecting duplicate identifiers within one source plan.
    """

    normalized = re.sub(r"[^A-Za-z0-9_.:-]+", "-", meal_slot.strip().lower())
    normalized = normalized.strip("-._:") or "meal"
    normalized = normalized[:MAX_NORMALIZED_MEAL_SLOT_LENGTH]
    digest = hashlib.sha256(meal_slot.encode("utf-8")).hexdigest()[
        :MEAL_SLOT_DIGEST_LENGTH
    ]
    return f"day-{day}.{normalized}-{digest}"
