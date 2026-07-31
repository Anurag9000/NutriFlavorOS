"""Shared quantity normalization for inventory operations."""

from __future__ import annotations

from typing import Tuple

from backend.domain.ingredients import _UNIT_ALIASES


def normalize_quantity_values(
    quantity_min: float,
    quantity_max: float,
    unit: str,
) -> Tuple[float, float, str]:
    """Normalize a quantity range to the parser's canonical unit.

    Unknown units are rejected instead of being silently treated as counts.
    """

    if quantity_min < 0 or quantity_max < quantity_min:
        raise ValueError("Invalid quantity range")
    normalized_unit = " ".join(unit.lower().strip().split())
    if normalized_unit not in _UNIT_ALIASES:
        raise ValueError(f"Unsupported quantity unit: {unit}")
    _, canonical_unit, multiplier = _UNIT_ALIASES[normalized_unit]
    return quantity_min * multiplier, quantity_max * multiplier, canonical_unit
