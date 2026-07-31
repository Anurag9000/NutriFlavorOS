"""Conversions between SQLAlchemy user rows and validated planning profiles."""

from __future__ import annotations

from typing import List

from backend.database import DBUser
from backend.models import Gender, Goal, UserProfile


REQUIRED_PROFILE_FIELDS = (
    "age",
    "weight_kg",
    "height_cm",
    "gender",
    "activity_level",
    "goal",
)


class IncompleteProfileError(ValueError):
    def __init__(self, missing_fields: List[str]):
        self.missing_fields = missing_fields
        super().__init__(
            "Complete the nutrition profile before generating plans: "
            + ", ".join(missing_fields)
        )

    def to_detail(self):
        return {
            "code": "profile_incomplete",
            "message": str(self),
            "missing_fields": self.missing_fields,
        }


def _list_or_empty(value):
    return list(value) if isinstance(value, list) else []


def missing_profile_fields(user: DBUser) -> List[str]:
    missing = []
    for field in REQUIRED_PROFILE_FIELDS:
        value = getattr(user, field, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    if user.gender is not None and user.gender not in {item.value for item in Gender}:
        missing.append("gender")
    if user.goal is not None and user.goal not in {item.value for item in Goal}:
        missing.append("goal")
    return sorted(set(missing))


def profile_is_complete(user: DBUser) -> bool:
    return not missing_profile_fields(user)


def db_user_to_profile(user: DBUser) -> UserProfile:
    """Return a complete validated profile or fail without invented physiology."""

    missing = missing_profile_fields(user)
    if missing:
        raise IncompleteProfileError(missing)

    return UserProfile(
        name=user.name or "New User",
        age=int(user.age),
        weight_kg=float(user.weight_kg),
        height_cm=float(user.height_cm),
        gender=Gender(user.gender),
        activity_level=float(user.activity_level),
        goal=Goal(user.goal),
        liked_ingredients=_list_or_empty(user.liked_ingredients),
        disliked_ingredients=_list_or_empty(user.disliked_ingredients),
        allergies=_list_or_empty(getattr(user, "allergies", None)),
        dietary_restrictions=_list_or_empty(user.dietary_restrictions),
        health_conditions=_list_or_empty(user.health_conditions),
        medications=_list_or_empty(getattr(user, "medications", None)),
        target_calories=getattr(user, "target_calories", None),
        target_protein_g=getattr(user, "target_protein_g", None),
        target_carbs_g=getattr(user, "target_carbs_g", None),
        target_fat_g=getattr(user, "target_fat_g", None),
    )


def apply_profile(user: DBUser, profile: UserProfile) -> DBUser:
    user.name = profile.name or user.name or "New User"
    user.age = profile.age
    user.weight_kg = profile.weight_kg
    user.height_cm = profile.height_cm
    user.gender = profile.gender.value
    user.activity_level = profile.activity_level
    user.goal = profile.goal.value
    user.liked_ingredients = list(profile.liked_ingredients)
    user.disliked_ingredients = list(profile.disliked_ingredients)
    user.allergies = list(profile.allergies)
    user.dietary_restrictions = list(profile.dietary_restrictions)
    user.health_conditions = list(profile.health_conditions)
    user.medications = list(profile.medications)
    user.target_calories = profile.target_calories
    user.target_protein_g = profile.target_protein_g
    user.target_carbs_g = profile.target_carbs_g
    user.target_fat_g = profile.target_fat_g
    return user
