"""
ML Package for NutriFlavorOS
Contains advanced ML models for taste prediction, meal planning, and personalization
"""
from .taste_predictor import DeepTastePredictor
from .meal_planner_rl import RLMealPlanner
from .recipe_vision import RecipeVisionAnalyzer
from .recipe_generator_nlp import NLPRecipeGenerator
from .health_predictor import HealthOutcomePredictor

__all__ = [
    'DeepTastePredictor',
    'RLMealPlanner',
    'RecipeVisionAnalyzer',
    'NLPRecipeGenerator',
    'HealthOutcomePredictor'
]
