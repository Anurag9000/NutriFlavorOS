"""Deterministic leakage-aware dataset splitting utilities."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Dict, Sequence, Tuple


def _validate_ratios(ratios: Sequence[float]) -> Tuple[float, float, float]:
    if len(ratios) != 3 or any(value < 0 for value in ratios):
        raise ValueError("ratios must contain three non-negative values")
    total = sum(ratios)
    if total <= 0:
        raise ValueError("split ratios must sum to a positive value")
    normalized = tuple(value / total for value in ratios)
    return normalized  # type: ignore[return-value]


def stable_bucket(value: str, *, seed: int = 0) -> float:
    digest = hashlib.sha256(f"{seed}:{value}".encode("utf-8")).digest()
    integer = int.from_bytes(digest[:8], "big")
    return integer / float(2**64)


def group_aware_split(row_ids: Sequence[str], group_ids: Sequence[str], *, ratios: Sequence[float] = (0.8, 0.1, 0.1), seed: int = 0) -> Dict[str, str]:
    """Assign every row in a group to the same deterministic split."""
    if len(row_ids) != len(group_ids):
        raise ValueError("row_ids and group_ids must have equal length")
    train_ratio, validation_ratio, _ = _validate_ratios(ratios)
    group_assignment: Dict[str, str] = {}
    result: Dict[str, str] = {}
    for row_id, group_id in zip(row_ids, group_ids):
        if row_id in result:
            raise ValueError(f"Duplicate row identifier: {row_id}")
        if group_id not in group_assignment:
            bucket = stable_bucket(group_id, seed=seed)
            group_assignment[group_id] = "train" if bucket < train_ratio else "validation" if bucket < train_ratio + validation_ratio else "test"
        result[row_id] = group_assignment[group_id]
    return result


def temporal_split(row_ids: Sequence[str], timestamps: Sequence[datetime], *, ratios: Sequence[float] = (0.8, 0.1, 0.1)) -> Dict[str, str]:
    """Chronologically split rows so no later example enters an earlier partition."""
    if len(row_ids) != len(timestamps):
        raise ValueError("row_ids and timestamps must have equal length")
    train_ratio, validation_ratio, _ = _validate_ratios(ratios)
    ordered = sorted(zip(row_ids, timestamps), key=lambda item: (item[1], item[0]))
    if len({row_id for row_id, _ in ordered}) != len(ordered):
        raise ValueError("row identifiers must be unique")
    n = len(ordered)
    train_end = round(n * train_ratio)
    validation_end = round(n * (train_ratio + validation_ratio))
    result: Dict[str, str] = {}
    for index, (row_id, _) in enumerate(ordered):
        result[row_id] = "train" if index < train_end else "validation" if index < validation_end else "test"
    return result


def assert_no_group_leakage(assignments: Dict[str, str], row_to_group: Dict[str, str]) -> None:
    observed: Dict[str, str] = {}
    for row_id, split in assignments.items():
        group = row_to_group[row_id]
        previous = observed.setdefault(group, split)
        if previous != split:
            raise ValueError(f"Group leakage detected for {group}: {previous} and {split}")
