"""API services package."""

# Import the additive household-plan lifecycle mapping before any service uses
# DBMealPlan. This preserves the historical database module import path while
# ensuring migration 20260802_0013 columns participate in ORM queries and
# Base.metadata test schemas.
from backend import meal_plan_lifecycle_models as _meal_plan_lifecycle_models

from .recipedb_service import RecipeDBService
from .flavordb_service import FlavorDBService
from .sustainablefooddb_service import SustainableFoodDBService
from .dietrxdb_service import DietRxDBService

__all__ = [
    "RecipeDBService",
    "FlavorDBService",
    "SustainableFoodDBService",
    "DietRxDBService",
]
