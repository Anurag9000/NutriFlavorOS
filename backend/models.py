from typing import List, Optional, Dict
from pydantic import BaseModel
from enum import Enum

class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"

class Goal(str, Enum):
    WEIGHT_LOSS = "weight_loss"
    MAINTENANCE = "maintenance"
    MUSCLE_GAIN = "muscle_gain"

class UserProfile(BaseModel):
    # Biometrics
    name: Optional[str] = None
    age: int
    weight_kg: float
    height_cm: float
    gender: Gender
    activity_level: float # 1.2 to 1.9 multiplier
    goal: Goal
    
    # Preferences
    liked_ingredients: List[str] = []
    disliked_ingredients: List[str] = []
    dietary_restrictions: List[str] = []
    
    # Health (optional)
    health_conditions: List[str] = []  # e.g., ["diabetes", "hypertension"]
    medications: List[str] = []  # For drug-food interaction checks

class NutrientTarget(BaseModel):
    calories: int
    protein_g: int
    carbs_g: int
    fat_g: int
    micro_nutrients: Dict[str, float] = {}

class Ingredient(BaseModel):
    name: str
    flavor_compounds: List[str] = []
    flavor_profile: Dict[str, float] = {} # e.g. {"sweet": 0.8, "bitter": 0.1}

class Recipe(BaseModel):
    id: str
    name: str
    description: str
    image_url: Optional[str] = None
    ingredients: List[str]
    calories: int
    macros: Dict[str, int] # {"protein": 20, "carbs": 30, "fat": 10}
    flavor_profile: Dict[str, float] = {} # Aggregated or specific
    tags: List[str] = []
    cuisine: Optional[str] = None  # For variety tracking
    instructions: List[str] = []  # Cooking steps

class DailyPlan(BaseModel):
    day: int
    meals: Dict[str, Recipe] # "breakfast": Recipe(...)
    total_stats: Dict[str, float]
    scores: Dict[str, float] # {"health": 0.9, "taste": 0.85, "variety": 0.95}

class PlanResponse(BaseModel):
    user_id: str
    days: List[DailyPlan]
    shopping_list: Optional[Dict[str, Dict]] = None  # Categorized shopping list
    prep_timeline: Optional[Dict[int, List[str]]] = None  # Day -> prep tasks
    overall_stats: Optional[Dict] = None  # Overall plan statistics

