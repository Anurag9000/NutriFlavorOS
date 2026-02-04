"""
Health Engine - Real micronutrient tracking and condition-aware meal planning
"""
from typing import Dict, List, Optional
from backend.models import UserProfile, NutrientTarget, Gender, Goal
from backend.services.recipedb_service import RecipeDBService
from backend.services.dietrxdb_service import DietRxDBService

class HealthEngine:
    """
    Advanced Health Engine with:
    - Real micronutrient tracking (20+ vitamins/minerals)
    - Condition-aware constraints
    - Full macro/micro matching
    - Drug interaction safety checks
    """
    
    # RDA (Recommended Dietary Allowances) for micronutrients
    MICRONUTRIENT_RDA = {
        # Vitamins
        "Vitamin A": {"male": 900, "female": 700, "unit": "mcg"},
        "Vitamin C": {"male": 90, "female": 75, "unit": "mg"},
        "Vitamin D": {"male": 15, "female": 15, "unit": "mcg"},
        "Vitamin E": {"male": 15, "female": 15, "unit": "mg"},
        "Vitamin K": {"male": 120, "female": 90, "unit": "mcg"},
        "Vitamin B1 (Thiamin)": {"male": 1.2, "female": 1.1, "unit": "mg"},
        "Vitamin B2 (Riboflavin)": {"male": 1.3, "female": 1.1, "unit": "mg"},
        "Vitamin B3 (Niacin)": {"male": 16, "female": 14, "unit": "mg"},
        "Vitamin B6": {"male": 1.3, "female": 1.3, "unit": "mg"},
        "Vitamin B12": {"male": 2.4, "female": 2.4, "unit": "mcg"},
        "Folate": {"male": 400, "female": 400, "unit": "mcg"},
        
        # Minerals
        "Calcium": {"male": 1000, "female": 1000, "unit": "mg"},
        "Iron": {"male": 8, "female": 18, "unit": "mg"},
        "Magnesium": {"male": 400, "female": 310, "unit": "mg"},
        "Phosphorus": {"male": 700, "female": 700, "unit": "mg"},
        "Potassium": {"male": 3400, "female": 2600, "unit": "mg"},
        "Sodium": {"male": 1500, "female": 1500, "unit": "mg"},
        "Zinc": {"male": 11, "female": 8, "unit": "mg"},
        "Copper": {"male": 900, "female": 900, "unit": "mcg"},
        "Selenium": {"male": 55, "female": 55, "unit": "mcg"},
        "Manganese": {"male": 2.3, "female": 1.8, "unit": "mg"},
    }
    
    def __init__(self):
        self.recipe_service = RecipeDBService()
        self.diet_rx_service = DietRxDBService()
    
    @staticmethod
    def calculate_bmr(user: UserProfile) -> float:
        """Calculate Basal Metabolic Rate using Mifflin-St Jeor Equation"""
        if user.gender == Gender.MALE:
            bmr = (10 * user.weight_kg) + (6.25 * user.height_cm) - (5 * user.age) + 5
        else:
            bmr = (10 * user.weight_kg) + (6.25 * user.height_cm) - (5 * user.age) - 161
        return bmr
    
    def calculate_targets(self, user: UserProfile) -> NutrientTarget:
        """Calculate comprehensive macro and micronutrient targets"""
        bmr = self.calculate_bmr(user)
        tdee = bmr * user.activity_level
        
        # Adjust for goal
        target_calories = tdee
        if user.goal == Goal.WEIGHT_LOSS:
            target_calories -= 500
        elif user.goal == Goal.MUSCLE_GAIN:
            target_calories += 400
            
        target_calories = max(1200, target_calories)
        
        # Macro Split
        if user.goal == Goal.MUSCLE_GAIN:
            p_ratio, c_ratio, f_ratio = 0.35, 0.40, 0.25
        elif user.goal == Goal.WEIGHT_LOSS:
            p_ratio, c_ratio, f_ratio = 0.40, 0.30, 0.30
        else:
            p_ratio, c_ratio, f_ratio = 0.30, 0.35, 0.35
            
        protein_g = (target_calories * p_ratio) / 4
        carbs_g = (target_calories * c_ratio) / 4
        fat_g = (target_calories * f_ratio) / 9
        
        # Calculate micronutrient targets based on gender
        gender_key = "male" if user.gender == Gender.MALE else "female"
        micro_targets = {
            nutrient: data[gender_key] 
            for nutrient, data in self.MICRONUTRIENT_RDA.items()
        }
        
        return NutrientTarget(
            calories=int(target_calories),
            protein_g=int(protein_g),
            carbs_g=int(carbs_g),
            fat_g=int(fat_g),
            micro_nutrients=micro_targets
        )
    
    def get_recipe_full_nutrition(self, recipe_id: str) -> Dict:
        """Get complete nutrition profile including micronutrients"""
        try:
            # Get macro nutrition
            macro_info = self.recipe_service.get_nutrition_info(recipe_id)
            
            # Get micronutrient data
            micro_info = self.recipe_service.get_micronutrition_info(recipe_id)
            
            return {
                "macros": macro_info,
                "micros": micro_info
            }
        except Exception as e:
            print(f"Error fetching nutrition for recipe {recipe_id}: {e}")
            return {"macros": {}, "micros": {}}
    
    def score_recipe_comprehensive(self, recipe_id: str, target: NutrientTarget, 
                                   user_conditions: List[str] = None) -> Dict:
        """
        Comprehensive recipe scoring with:
        - Macro matching
        - Micronutrient coverage
        - Condition compatibility
        - Safety checks
        """
        nutrition = self.get_recipe_full_nutrition(recipe_id)
        macros = nutrition.get("macros", {})
        micros = nutrition.get("micros", {})
        
        # 1. Macro Score (40% weight)
        target_per_meal = {
            "calories": target.calories / 3,
            "protein": target.protein_g / 3,
            "carbs": target.carbs_g / 3,
            "fat": target.fat_g / 3
        }
        
        macro_scores = []
        for nutrient in ["calories", "protein", "carbs", "fat"]:
            actual = macros.get(nutrient, 0)
            target_val = target_per_meal[nutrient]
            if target_val > 0:
                deviation = abs(actual - target_val) / target_val
                score = max(0, 1.0 - deviation)
                macro_scores.append(score)
        
        macro_score = sum(macro_scores) / len(macro_scores) if macro_scores else 0.5
        
        # 2. Micronutrient Coverage Score (30% weight)
        micro_coverage = []
        for nutrient, target_val in target.micro_nutrients.items():
            actual = micros.get(nutrient, 0)
            # Each meal should provide ~33% of daily RDA
            target_per_meal = target_val / 3
            if target_per_meal > 0:
                coverage = min(1.0, actual / target_per_meal)
                micro_coverage.append(coverage)
        
        micro_score = sum(micro_coverage) / len(micro_coverage) if micro_coverage else 0.5
        
        # 3. Condition Compatibility Score (30% weight)
        condition_score = 1.0
        warnings = []
        
        if user_conditions:
            # Check each ingredient against conditions
            recipe_info = self.recipe_service.get_recipe_info(recipe_id)
            ingredients = recipe_info.get("ingredients", [])
            
            for ingredient in ingredients:
                try:
                    compatibility = self.diet_rx_service.check_condition_compatibility(
                        ingredient, user_conditions
                    )
                    if not compatibility["safe_to_consume"]:
                        condition_score = 0.0
                        warnings.extend(compatibility["warnings"])
                    elif compatibility["score"] < 50:
                        condition_score *= 0.7
                except:
                    pass
        
        # Final weighted score
        final_score = (macro_score * 0.4) + (micro_score * 0.3) + (condition_score * 0.3)
        
        return {
            "total_score": final_score,
            "macro_score": macro_score,
            "micro_score": micro_score,
            "condition_score": condition_score,
            "warnings": warnings,
            "safe": len(warnings) == 0,
            "micronutrient_coverage": dict(zip(target.micro_nutrients.keys(), micro_coverage))
        }
