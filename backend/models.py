from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class Goal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MAINTENANCE = "maintenance"
    MUSCLE_GAIN = "muscle_gain"


class IngredientParseStatus(str, Enum):
    NORMALIZED = "normalized"
    PARTIAL = "partial"
    UNQUANTIFIED = "unquantified"


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


class IngredientLine(BaseModel):
    """Parsed representation of one ingredient statement.

    Quantity ranges are retained rather than collapsed to a fabricated point
    estimate. ``canonical_*`` fields are populated only when conversion is
    dimensionally safe.
    """

    raw: str
    name: str
    quantity_min: Optional[float] = Field(default=None, ge=0)
    quantity_max: Optional[float] = Field(default=None, ge=0)
    unit: Optional[str] = None
    canonical_quantity_min: Optional[float] = Field(default=None, ge=0)
    canonical_quantity_max: Optional[float] = Field(default=None, ge=0)
    canonical_unit: Optional[str] = None
    parse_status: IngredientParseStatus = IngredientParseStatus.UNQUANTIFIED

    @model_validator(mode="after")
    def validate_ranges(self):
        if (
            self.quantity_min is not None
            and self.quantity_max is not None
            and self.quantity_max < self.quantity_min
        ):
            raise ValueError("quantity_max cannot be less than quantity_min")
        if (
            self.canonical_quantity_min is not None
            and self.canonical_quantity_max is not None
            and self.canonical_quantity_max < self.canonical_quantity_min
        ):
            raise ValueError("canonical_quantity_max cannot be less than canonical_quantity_min")
        return self


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
    ingredient_lines: List[IngredientLine] = Field(default_factory=list)
    servings: float = Field(default=1.0, gt=0, le=1000)
    calories: int = Field(ge=0)
    macros: Dict[str, float] = Field(default_factory=dict)
    flavor_profile: Dict[str, float] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)
    cuisine: Optional[str] = None
    instructions: List[str] = Field(default_factory=list)
    estimated_cost: Optional[float] = Field(default=0.0, ge=0)
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    source_version: Optional[str] = None
    nutrition_basis: str = Field(default="per_serving", pattern=r"^(per_serving|per_100g|per_recipe|unknown)$")


class DailyPlan(BaseModel):
    day: int = Field(ge=1)
    meals: Dict[str, Recipe]
    portions: Dict[str, float] = Field(default_factory=dict)
    total_stats: Dict[str, Any]
    scores: Dict[str, float]


class OptimizationSummary(BaseModel):
    method: str
    deterministic: bool = True
    objective_score: float
    beam_width: int = Field(ge=1)
    candidate_count: int = Field(ge=0)
    slot_count: int = Field(ge=0)
    portion_options: List[float] = Field(default_factory=list)
    repeat_window_slots: int = Field(ge=0)
    max_recipe_occurrences: int = Field(ge=1)
    relaxations: List[str] = Field(default_factory=list)
    slot_candidate_counts: Dict[str, int] = Field(default_factory=dict)


class PlanResponse(BaseModel):
    user_id: str
    days: List[DailyPlan]
    shopping_list: Optional[Dict[str, Dict[str, Any]]] = None
    prep_timeline: Optional[Dict[int, List[str]]] = None
    overall_stats: Optional[Dict[str, Any]] = None
    optimization: Optional[OptimizationSummary] = None
    warnings: List[str] = Field(default_factory=list)
