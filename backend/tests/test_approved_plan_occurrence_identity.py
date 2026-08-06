"""Contract tests for stable approved-plan occurrence identities."""

from backend.domain.approved_plan_occurrence_identity import (
    MAX_NORMALIZED_MEAL_SLOT_LENGTH,
    approved_plan_occurrence_id,
)
from backend.services.household_plan_occurrence_service import _occurrence_id


def test_occurrence_identity_is_stable_and_readable() -> None:
    assert approved_plan_occurrence_id(1, "Dinner") == (
        "day-1.dinner-216713d08860cfa0"
    )
    assert approved_plan_occurrence_id(1, "Late Snack") == (
        "day-1.late-snack-7486e2ac9827afeb"
    )


def test_digest_distinguishes_labels_with_same_readable_normalization() -> None:
    first = approved_plan_occurrence_id(2, "Late Snack")
    second = approved_plan_occurrence_id(2, "late  snack")

    assert first.startswith("day-2.late-snack-")
    assert second.startswith("day-2.late-snack-")
    assert first != second


def test_empty_normalization_uses_bounded_meal_fallback() -> None:
    assert approved_plan_occurrence_id(3, "!!!") == (
        "day-3.meal-e84c538e7fe25073"
    )

    long_identifier = approved_plan_occurrence_id(4, "x" * 100)
    readable, digest = long_identifier.rsplit("-", 1)
    assert readable == f"day-4.{('x' * MAX_NORMALIZED_MEAL_SLOT_LENGTH)}"
    assert len(digest) == 16


def test_service_compatibility_wrapper_uses_public_contract() -> None:
    for day, meal_slot in (
        (1, "Breakfast"),
        (2, "Late Snack"),
        (7, "Chef's special / dinner"),
    ):
        assert _occurrence_id(day, meal_slot) == approved_plan_occurrence_id(
            day,
            meal_slot,
        )
