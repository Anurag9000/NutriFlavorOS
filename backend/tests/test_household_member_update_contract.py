from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.domain.household_access import HouseholdMemberUpdate


@pytest.mark.parametrize(
    "field",
    [
        "display_name",
        "role",
        "servings_multiplier",
        "allergies",
        "dietary_restrictions",
        "disliked_ingredients",
        "active",
    ],
)
def test_non_clearable_member_fields_reject_explicit_null(field: str):
    with pytest.raises(ValidationError, match="cannot be null"):
        HouseholdMemberUpdate.model_validate({field: None})


def test_optional_nutrition_targets_can_be_cleared_explicitly():
    value = HouseholdMemberUpdate.model_validate(
        {
            "target_calories": None,
            "target_protein_g": None,
            "target_carbs_g": None,
            "target_fat_g": None,
        }
    )
    assert value.model_dump(exclude_unset=True) == {
        "target_calories": None,
        "target_protein_g": None,
        "target_carbs_g": None,
        "target_fat_g": None,
    }
