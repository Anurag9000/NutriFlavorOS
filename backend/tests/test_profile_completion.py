from types import SimpleNamespace
import pytest
from backend.utils.user_profiles import IncompleteProfileError, db_user_to_profile, missing_profile_fields, profile_is_complete


def _user(**updates):
    values = dict(name="User", age=None, weight_kg=None, height_cm=None, gender=None, activity_level=None, goal=None,
                  liked_ingredients=[], disliked_ingredients=[], allergies=[], dietary_restrictions=[], health_conditions=[], medications=[],
                  target_calories=None, target_protein_g=None, target_carbs_g=None, target_fat_g=None)
    values.update(updates)
    return SimpleNamespace(**values)


def test_missing_profile_is_explicit_and_never_defaulted():
    user = _user()
    assert set(missing_profile_fields(user)) == {"age", "weight_kg", "height_cm", "gender", "activity_level", "goal"}
    assert profile_is_complete(user) is False
    with pytest.raises(IncompleteProfileError) as error:
        db_user_to_profile(user)
    assert "missing_fields" in error.value.to_detail()


def test_complete_profile_round_trips_without_invented_values():
    user = _user(age=42, weight_kg=81.5, height_cm=181.0, gender="male", activity_level=1.55, goal="maintenance")
    profile = db_user_to_profile(user)
    assert profile.age == 42
    assert profile.weight_kg == 81.5
    assert profile.height_cm == 181.0
