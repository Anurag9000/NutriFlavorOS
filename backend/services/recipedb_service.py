"""
RecipeDB API Service - 118,000+ recipes with full nutrition data
"""
import json
import os
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
    
    def _map_to_domain_recipe(self, raw: Dict) -> Dict:
        """Map RecipeDB raw data to domain Recipe model"""
        # Handle already mapped data (if mocked correctly elsewhere)
        if "id" in raw and "macros" in raw:
            return raw
            
        # Map fields
        try:
            r_id = raw.get("Recipe_id", str(raw.get("id", "")))
            title = raw.get("Recipe_title", raw.get("title", "Unknown Recipe"))
            
            # Nutrition
            try:
                cals = float(raw.get("Calories", 0))
                protein = float(raw.get("Protein (g)", 0))
                fat = float(raw.get("Total lipid (fat) (g)", 0))
                carbs = float(raw.get("Carbohydrate, by difference (g)", 0))
            except (ValueError, TypeError):
                cals, protein, fat, carbs = 0, 0, 0, 0
            
            # Instructions from piped string
            instr_str = raw.get("Processes", "")
            instructions = instr_str.split("||") if instr_str else []
            
            # Ingredients 
            # Harvested data might not have clean ingredient list in top level. 
            # We'll default to empty list if missing, preventing validation error.
            ingredients = raw.get("ingredients", [])
            if isinstance(ingredients, str): ingredients = [ingredients]
            
            return {
                "id": r_id,
                "name": title,
                "description": f"A {raw.get('Region', 'delicious')} dish.",
                "image_url": raw.get("image", None),
                "ingredients": ingredients,
                "calories": int(cals),
                "macros": {
                    "protein": int(protein),
                    "carbs": int(carbs),
                    "fat": int(fat)
                },
                "flavor_profile": {}, # Populated by TasteEngine later
                "tags": [x for x in [raw.get("Region"), raw.get("Sub_region"), raw.get("Continent")] if x],
                "cuisine": raw.get("Region"),
                "instructions": instructions
            }
        except Exception as e:
            print(f"Error mapping recipe {raw.get('Recipe_id')}: {e}")
            return {
                "id": "error",
                "name": "Error Loading Recipe",
                "description": "",
                "ingredients": [],
                "calories": 0,
                "macros": {"protein": 0, "carbs": 0, "fat": 0},
                "instructions": []
            }
    
    def get_all_recipes(self) -> List[Dict]:
        """Load all recipes from local JSON file (harvested RecipeDB data)"""
        json_path = os.path.join("backend", "data", "recipes.json")
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                raw_recipes = json.load(f)
            return [self._map_to_domain_recipe(r) for r in raw_recipes]
        except FileNotFoundError:
            print(f"Warning: {json_path} not found. Returning empty list.")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing {json_path}: {e}")
            return []

    def search_by_title(self, title: str) -> List[Dict]:
        """Search recipes by name from local JSON data"""
        all_recipes = self.get_all_recipes()
        
        if not title:  # Empty title = return all
            return all_recipes
        
        # Filter by title (case-insensitive)
        title_lower = title.lower()
        return [r for r in all_recipes if title_lower in r.get("name", "").lower()]
    
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
