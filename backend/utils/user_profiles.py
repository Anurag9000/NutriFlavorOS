"""Conversions between SQLAlchemy user rows and validated API profiles."""

from __future__ import annotations

from backend.database import DBUser
from backend.models import Gender, Goal, UserProfile


def _list_or_empty(value):
    return list(value) if isinstance(value, list) else []


def db_user_to_profile(user: DBUser) -> UserProfile:
    """Return a complete validated profile, including defaults for legacy rows."""

    return UserProfile(
        name=user.name or "New User",
        age=user.age if user.age is not None else 30,
        weight_kg=user.weight_kg if user.weight_kg is not None else 70.0,
        height_cm=user.height_cm if user.height_cm is not None else 170.0,
        gender=user.gender if user.gender in {item.value for item in Gender} else Gender.OTHER,
        activity_level=user.activity_level if user.activity_level is not None else 1.4,
        goal=user.goal if user.goal in {item.value for item in Goal} else Goal.MAINTENANCE,
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
