from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Goal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MAINTENANCE = "maintenance"
    MUSCLE_GAIN = "muscle_gain"


class UserProfile(BaseModel):
    """User-owned planning inputs.

    Medical conditions and medications are retained for transparency, but the
    current planner does not claim clinical validation. Allergies are modeled
    separately from preferences so safety filters do not depend on string
    prefixes embedded in ``disliked_ingredients``.
    """

    name: Optional[str] = None
    age: int = Field(ge=18, le=120)
    weight_kg: float = Field(gt=0, le=500)
    height_cm: float = Field(gt=0, le=300)
    gender: Gender
    activity_level: float = Field(ge=1.0, le=3.0)
    goal: Goal

    liked_ingredients: List[str] = Field(default_factory=list)
    disliked_ingredients: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    dietary_restrictions: List[str] = Field(default_factory=list)

    health_conditions: List[str] = Field(default_factory=list)
    medications: List[str] = Field(default_factory=list)

    target_calories: Optional[int] = Field(default=None, gt=0)
    target_protein_g: Optional[int] = Field(default=None, ge=0)
    target_carbs_g: Optional[int] = Field(default=None, ge=0)
    target_fat_g: Optional[int] = Field(default=None, ge=0)


class NutrientTarget(BaseModel):
    calories: int = Field(gt=0)
    protein_g: int = Field(ge=0)
    carbs_g: int = Field(ge=0)
    fat_g: int = Field(ge=0)
    micro_nutrients: Dict[str, float] = Field(default_factory=dict)


class Ingredient(BaseModel):
    name: str
    flavor_compounds: List[str] = Field(default_factory=list)
    flavor_profile: Dict[str, float] = Field(default_factory=dict)


class Recipe(BaseModel):
    id: str
    name: str
    description: str
    image_url: Optional[str] = None
    ingredients: List[str] = Field(default_factory=list)
    calories: int = Field(ge=0)
    macros: Dict[str, float] = Field(default_factory=dict)
    flavor_profile: Dict[str, float] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    cuisine: Optional[str] = None
    instructions: List[str] = Field(default_factory=list)
    estimated_cost: Optional[float] = Field(default=0.0, ge=0)


class DailyPlan(BaseModel):
    day: int = Field(ge=1)
    meals: Dict[str, Recipe]
    total_stats: Dict[str, Any]
    scores: Dict[str, float]


class PlanResponse(BaseModel):
    user_id: str
    days: List[DailyPlan]
    shopping_list: Optional[Dict[str, Dict[str, Any]]] = None
    prep_timeline: Optional[Dict[int, List[str]]] = None
    overall_stats: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)
