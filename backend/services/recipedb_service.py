"""
RecipeDB API Service - 118,000+ recipes with full nutrition data
"""
from typing import List, Dict, Any, Optional
from backend.services.base_service import BaseAPIService
from backend.config import APIConfig

class RecipeDBService(BaseAPIService):
    """Service for interacting with RecipeDB API"""
    
    def __init__(self):
        super().__init__(
            base_url=APIConfig.RECIPEDB_BASE_URL,
            api_key=APIConfig.RECIPEDB_API_KEY
        )
    
    def get_recipe_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get basic recipe information"""
        return self._make_request(f"recipesInfo", params={"id": recipe_id})
    
    def get_nutrition_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get macro nutrition information"""
        return self._make_request(f"nutritionInfo", params={"id": recipe_id})
    
    def get_micronutrition_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get micronutrient details (vitamins, minerals)"""
        return self._make_request(f"micronutritionInfo", params={"id": recipe_id})
    
    def get_recipe_instructions(self, recipe_id: str) -> List[str]:
        """Get step-by-step cooking instructions"""
        result = self._make_request(f"instructions/{recipe_id}")
        return result.get("instructions", [])
    
    def search_by_cuisine(self, cuisine: str, limit: int = 50) -> List[Dict]:
        """Search recipes by cuisine type"""
        return self._make_request(f"recipes_cuisine/cuisine/{cuisine}", 
                                 params={"limit": limit})
    
    def search_by_calories(self, min_cal: int, max_cal: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by calorie range"""
        return self._make_request("calories", 
                                 params={"min": min_cal, "max": max_cal, "limit": limit})
    
    def search_by_protein(self, min_protein: int, max_protein: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by protein range"""
        return self._make_request("protein-range", 
                                 params={"min": min_protein, "max": max_protein, "limit": limit})
    
    def search_by_carbs(self, min_carbs: int, max_carbs: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by carb range"""
        return self._make_request("recipes-by-carbs", 
                                 params={"min": min_carbs, "max": max_carbs, "limit": limit})
    
    def search_by_title(self, title: str) -> List[Dict]:
        """Search recipes by name"""
        return self._make_request("recipeByTitle", params={"title": title})
    
    def get_recipes_by_day(self, day: str) -> List[Dict]:
        """Get recipes suitable for specific meal time (breakfast/lunch/dinner)"""
        return self._make_request("recipesDay", params={"day": day})
    
    def get_recipes_by_method(self, method: str, limit: int = 50) -> List[Dict]:
        """Get recipes by cooking method (bake, fry, grill, steam, etc.)"""
        return self._make_request(f"recipes-method/{method}", params={"limit": limit})
    
    def get_recipes_by_utensils(self, utensils: List[str], limit: int = 50) -> List[Dict]:
        """Filter recipes by available kitchen equipment"""
        return self._make_request("bydetails/utensils", 
                                 params={"utensils": ",".join(utensils), "limit": limit})
    
    def get_regional_diet(self, region: str) -> Dict[str, Any]:
        """Get traditional dietary patterns for a region"""
        return self._make_request("region-diet", params={"region": region})
    
    def get_diet_specific_recipes(self, diet_type: str, limit: int = 50) -> List[Dict]:
        """Get recipes for specific diets (keto, vegan, paleo, etc.)"""
        return self._make_request("recipe-diet", params={"diet": diet_type, "limit": limit})
    
    def get_meal_plan_template(self, plan_type: str) -> Dict[str, Any]:
        """Get pre-made meal plan templates"""
        return self._make_request("meal-plan", params={"type": plan_type})
    
    def search_by_flavor(self, flavor: str, limit: int = 50) -> List[Dict]:
        """Search recipes by flavor profile"""
        return self._make_request(f"ingredients/flavor/{flavor}", params={"limit": limit})
    
    def advanced_search(self, 
                       cuisine: Optional[str] = None,
                       min_calories: Optional[int] = None,
                       max_calories: Optional[int] = None,
                       min_protein: Optional[int] = None,
                       diet_type: Optional[str] = None,
                       cooking_method: Optional[str] = None,
                       limit: int = 50) -> List[Dict]:
        """Advanced multi-filter search"""
        params = {"limit": limit}
        if cuisine:
            params["cuisine"] = cuisine
        if min_calories:
            params["min_calories"] = min_calories
        if max_calories:
            params["max_calories"] = max_calories
        if min_protein:
            params["min_protein"] = min_protein
        if diet_type:
            params["diet"] = diet_type
        if cooking_method:
            params["method"] = cooking_method
            
        return self._make_request("by-ingredients-categories-title", params=params)
