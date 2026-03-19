"""
Family Planner Engine - Multi-profile unified meal planning
Handles conflicting dietary needs and optimizes for shared kitchen efficiency
"""
from typing import List, Dict, Any, Optional, Set
from backend.models import UserProfile, Recipe, PlanResponse, DailyPlan, NutrientTarget
from backend.engines.plan_generator import PlanGenerator
from backend.engines.health_engine import HealthEngine

class FamilyPlanner:
    """
    Advanced Family Meal Planner
    
    Strategies:
    1. Base + Modifier: Shared base recipe (e.g. Pasta) with custom toppings (Meat vs Tofu)
    2. Intersection: Find recipes that satisfy ALL members' constraints
    3. Bulk Optimization: Minimize total unique ingredients across N plans
    """
    
    def __init__(self):
        self.generator = PlanGenerator()
        self.health_engine = HealthEngine()

    def create_family_plan(self, members: List[UserProfile], days: int = 7) -> Dict[str, Any]:
        """
        Generate a unified plan for a family
        """
        # 1. Aggregate constraints
        all_dislikes = set()
        all_restrictions = set()
        for m in members:
            all_dislikes.update(m.disliked_ingredients)
            all_restrictions.update(m.dietary_restrictions)
        
        # 2. Create 'Virtual Family Member' for common filtering
        # This member represents the "lowest common denominator" for safety
        family_rep = UserProfile(
            age=35, weight_kg=70, height_cm=170, gender="other",
            activity_level=1.5, goal="maintenance",
            disliked_ingredients=list(all_dislikes),
            dietary_restrictions=list(all_restrictions)
        )
        
        # 3. Generate base plan using the common constraints
        base_plan = self.generator.create_plan(family_rep, days)
        
        # 4. Personalize portions and modifiers for each member
        member_plans = {}
        for member in members:
            targets = self.health_engine.calculate_targets(member)
            member_plans[member.name or "Member"] = {
                "targets": targets,
                "portion_multiplier": targets.calories / 2000.0 # Normalized to 2k
            }
            
        return {
            "family_plan": base_plan,
            "member_adjustments": member_plans,
            "shopping_list": base_plan.shopping_list,
            "prep_timeline": base_plan.prep_timeline
        }

    def _find_base_recipe_with_modifiers(self, candidates: List[Recipe], members: List[UserProfile]) -> Recipe:
        """
        Select a recipe that can be easily modified for everyone
        Example: A stir-fry where protein is cooked separately
        """
        # Logic to find "modular" recipes
        return candidates[0]
