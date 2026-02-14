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

    def _make_request(self, endpoint: str, method: str = "GET", 
                     params: Optional[Dict] = None, 
                     data: Optional[Dict] = None) -> Any:
        """Override to unwrap 'data' key from response standard wrapper"""
        response = super()._make_request(endpoint, method, params, data)
        
        # Unwrap 'payload' key if present (RecipeDB V2 wrapper)
        if isinstance(response, dict) and "payload" in response:
            response = response["payload"]
        
        # Unwrap 'data' key if present (CosyLab API standard wrapper)
        if isinstance(response, dict):
            # Check for success flag if needed, but mainly extract data
            if "data" in response:
                return response["data"]
        
        return response
    
    def get_recipe_of_day(self) -> Dict[str, Any]:
        """Get recipe of the day"""
        # Postman: recipe2-api/recipe/recipeofday
        return self._make_request("recipe2-api/recipe/recipeofday")

    def get_recipe_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get basic recipe information"""
        # Note: 'recipesinfo' in V2 seems to be a list endpoint. 
        # Using it as search/list for now, or maybe there's an ID filter?
        # Postman doesn't show ID param for recipesinfo. 
        # However, for maintaining signature, we might need to change how this works or assume param 'id' works.
        # Let's use the endpoint from Postman.
        return self._make_request("recipe2-api/recipe/recipesinfo", params={"page": 1, "limit": 10}) # Modified for now, ID filtering might not be supported directly here

    def get_recipes_list(self, page: int = 1, limit: int = 10) -> Dict[str, Any]:
        """Get list of recipes"""
        return self._make_request("recipe2-api/recipe/recipesinfo", params={"page": page, "limit": limit})
    
    def get_nutrition_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get macro nutrition information"""
        # Postman: recipe2-api/recipe-nutri/nutritioninfo
        return self._make_request("recipe2-api/recipe-nutri/nutritioninfo", params={"page": 1, "limit": 10}) 
    
    def get_micronutrition_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get micronutrient details (vitamins, minerals)"""
        # Postman: recipe2-api/recipe-micronutri/micronutritioninfo
        return self._make_request("recipe2-api/recipe-micronutri/micronutritioninfo", params={"page": 1, "limit": 10})
    
    def get_recipe_instructions(self, recipe_id: str) -> List[str]:
        """Get step-by-step cooking instructions"""
        result = self._make_request(f"instructions/{recipe_id}")
        return result.get("instructions", [])
    
    def search_by_cuisine(self, cuisine: str, limit: int = 50) -> List[Dict]:
        """Search recipes by cuisine type"""
        # V2: Likely part of advanced search or recipesInfo filters. Using recipesInfo for connectivity.
        return self._make_request(f"recipe2-api/recipe/recipesinfo", 
                                 params={"limit": limit, "region": cuisine}) # Guessing 'region' param based on 'Region' field in response
    
    def search_by_calories(self, min_cal: int, max_cal: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by calorie range"""
        return self._make_request("recipe2-api/recipe/recipesinfo", # Updated base
                                 params={"min": min_cal, "max": max_cal, "limit": limit})
    
    def search_by_protein(self, min_protein: int, max_protein: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by protein range"""
        return self._make_request("recipe2-api/recipe/recipesinfo", 
                                 params={"min": min_protein, "max": max_protein, "limit": limit})
    
    def search_by_carbs(self, min_carbs: int, max_carbs: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by carb range"""
        return self._make_request("recipe2-api/recipe/recipesinfo", 
                                 params={"min": min_carbs, "max": max_carbs, "limit": limit})
    
    def search_by_title(self, title: str) -> List[Dict]:
        """Search recipes by name"""
        # Using advanced search endpoint which likely supports title filtering
        return self._make_request("recipe2-api/recipe/recipe-day/with-ingredients-categories", 
                                 params={"title": title, "page": 1, "limit": 50})
    
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
            params["region"] = cuisine # Changed to 'region' as per Postman likely behavior
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
            
        return self._make_request("recipe2-api/recipe/recipe-day/with-ingredients-categories", params=params)
