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

    def get_recipe_info(self, recipe_id: str) -> Optional[Dict[str, Any]]:
        """Get basic recipe information"""
        # Search by recipe_id
        result = self._make_request("recipe2-api/recipe/recipesinfo", params={"recipe_id": recipe_id})
        
        if isinstance(result, dict):
            return self._map_to_domain_recipe(result)
        if isinstance(result, list) and len(result) > 0:
            return self._map_to_domain_recipe(result[0])
        return None

    def get_recipes_list(self, page: int = 1, limit: int = 10) -> List[Dict]:
        """Get list of recipes"""
        result = self._make_request("recipe2-api/recipe/recipesinfo", params={"page": page, "limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def get_nutrition_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get macro nutrition information"""
        # Postman: recipe2-api/recipe-nutri/nutritioninfo
        # Assuming this also supports recipe_id filtering
        result = self._make_request("recipe2-api/recipe-nutri/nutritioninfo", params={"recipe_id": recipe_id})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return {}
    
    def get_micronutrition_info(self, recipe_id: str) -> Dict[str, Any]:
        """Get micronutrient details (vitamins, minerals)"""
        # Postman: recipe2-api/recipe-micronutri/micronutritioninfo
        result = self._make_request("recipe2-api/recipe-micronutri/micronutritioninfo", params={"recipe_id": recipe_id})
        if isinstance(result, list) and len(result) > 0:
            return result[0]
        return {}
    
    def get_recipe_instructions(self, recipe_id: str) -> List[str]:
        """Get step-by-step cooking instructions"""
        # Try both endpoints or fallback to info if needed
        # But commonly instructions are in the main info object now
        # We'll try the dedicated endpoint first
        try:
            result = self._make_request(f"instructions/{recipe_id}")
            if result and "instructions" in result:
                return result["instructions"]
        except:
            pass
        return []
    
    def search_by_cuisine(self, cuisine: str, limit: int = 50) -> List[Dict]:
        """Search recipes by cuisine type"""
        # V2: Likely part of advanced search or recipesInfo filters. Using recipesInfo for connectivity.
        result = self._make_request(f"recipe2-api/recipe/recipesinfo", 
                                 params={"limit": limit, "region": cuisine}) # Guessing 'region' param based on 'Region' field in response
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def search_by_calories(self, min_cal: int, max_cal: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by calorie range"""
        result = self._make_request("recipe2-api/recipe/recipesinfo", # Updated base
                                 params={"min": min_cal, "max": max_cal, "limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def search_by_protein(self, min_protein: int, max_protein: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by protein range"""
        result = self._make_request("recipe2-api/recipe/recipesinfo", 
                                 params={"min": min_protein, "max": max_protein, "limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def search_by_carbs(self, min_carbs: int, max_carbs: int, limit: int = 50) -> List[Dict]:
        """Filter recipes by carb range"""
        result = self._make_request("recipe2-api/recipe/recipesinfo", 
                                 params={"min": min_carbs, "max": max_carbs, "limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def _map_to_domain_recipe(self, raw: Dict) -> Dict:
        """Map RecipeDB raw data to domain Recipe model"""
        # Handle already mapped data (if mocked correctly elsewhere)
        if "id" in raw and "macros" in raw:
            return raw
            
        # Map fields
        try:
            # ID: try 'recipe_id' (new), 'Recipe_id' (old), 'id'
            r_id = str(raw.get("recipe_id") or raw.get("Recipe_id") or raw.get("id") or "")
            
            # Title: 'recipe_title' (new), 'Recipe_title' (old), 'title'
            title = raw.get("recipe_title") or raw.get("Recipe_title") or raw.get("title") or "Unknown Recipe"
            title = title.strip('"') # Remove extra quotes artifact
            
            # Nutrition
            # Try lowercase keys first (new API), then old capitalized keys
            try:
                # Calories
                per_serving_cals = float(raw.get("calories") or raw.get("Calories") or 0)
                
                # Macros (try various keys)
                # Protein
                total_protein = float(raw.get("protein") or raw.get("Protein (g)") or 0)
                # Fat
                total_fat = float(raw.get("fat") or raw.get("Total lipid (fat) (g)") or 0)
                # Carbs
                total_carbs = float(raw.get("carbohydrate") or raw.get("Carbohydrate, by difference (g)") or 0)
                
                # Check for Total Energy vs Per Serving scaling
                # New API might return per-serving directly. Old API had 'Energy (kcal)' -> total.
                total_energy = float(raw.get("Energy (kcal)") or 0)
                
                # If we have 'calories' directly (new API), use that and assume macros are aligned
                if raw.get("calories") is not None:
                    cals = per_serving_cals
                    protein = total_protein
                    fat = total_fat
                    carbs = total_carbs
                else:
                    # Old logic for scaling
                    if total_energy > 0 and per_serving_cals > 0:
                        ratio = per_serving_cals / total_energy
                        protein = total_protein * ratio
                        fat = total_fat * ratio
                        carbs = total_carbs * ratio
                        cals = per_serving_cals
                    else:
                        # Fallback: divide by servings if available
                        try:
                            servings = float(raw.get("servings", 1))
                            if servings <= 0: servings = 1
                        except (ValueError, TypeError):
                            servings = 1
                            
                        protein = total_protein / servings
                        fat = total_fat / servings
                        carbs = total_carbs / servings
                        cals = per_serving_cals if per_serving_cals > 0 else (total_energy / servings)
                    
            except (ValueError, TypeError):
                cals, protein, fat, carbs = 0, 0, 0, 0
            
            # Instructions from piped string or list
            instr_raw = raw.get("instructions") or raw.get("Processes", "")
            if isinstance(instr_raw, list):
                instructions = instr_raw
            else:
                instructions = instr_raw.split("||") if instr_raw else []
            
            # Ingredients 
            ing_raw = raw.get("ingredients", [])
            if isinstance(ing_raw, str):
                # Check for pipe or comma
                if "||" in ing_raw:
                     ingredients = ing_raw.split("||")
                else:
                     ingredients = [ing_raw] # or split by ','? Safer to keep as one if unsure
            elif isinstance(ing_raw, list):
                ingredients = ing_raw
            else:
                ingredients = []
            
            return {
                "id": r_id,
                "name": title,
                "description": f"A {raw.get('region') or raw.get('Region') or 'delicious'} dish.",
                "image_url": raw.get("image") or raw.get("img_url", None),
                "ingredients": ingredients,
                "calories": int(cals),
                "macros": {
                    "protein": int(protein),
                    "carbs": int(carbs),
                    "fat": int(fat)
                },
                "flavor_profile": {}, # Populated by TasteEngine later
                "tags": [x for x in [raw.get("region") or raw.get("Region"), raw.get("sub_region") or raw.get("Sub_region"), raw.get("continent") or raw.get("Continent")] if x],
                "cuisine": raw.get("region") or raw.get("Region"),
                "instructions": instructions,
                # Fix for missing Prep Time and Score
                "readyInMinutes": int(float(raw.get("total_time") or raw.get("readyInMinutes") or (float(raw.get("prep_time") or 0) + float(raw.get("cook_time") or 0)) or 30)),
                "healthScore": int(float(raw.get("health_score") or raw.get("healthScore") or 75))
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
        """Search recipes by name (API First)"""
        # Search via API
        # Note: API filtering parameter guessed as 'title' or 'q'. 
        result = self._make_request("recipe2-api/recipe/recipesinfo", 
                                 params={"limit": 10, "title": title})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def get_recipes_by_day(self, day: str) -> List[Dict]:
        """Get recipes suitable for specific meal time (breakfast/lunch/dinner)"""
        result = self._make_request("recipesDay", params={"day": day})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def get_recipes_by_method(self, method: str, limit: int = 50) -> List[Dict]:
        """Get recipes by cooking method (bake, fry, grill, steam, etc.)"""
        result = self._make_request(f"recipes-method/{method}", params={"limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def get_recipes_by_utensils(self, utensils: List[str], limit: int = 50) -> List[Dict]:
        """Filter recipes by available kitchen equipment"""
        result = self._make_request("bydetails/utensils", 
                                 params={"utensils": ",".join(utensils), "limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def get_regional_diet(self, region: str) -> Dict[str, Any]:
        """Get traditional dietary patterns for a region"""
        return self._make_request("region-diet", params={"region": region})
    
    def get_diet_specific_recipes(self, diet_type: str, limit: int = 50) -> List[Dict]:
        """Get recipes for specific diets (keto, vegan, paleo, etc.)"""
        result = self._make_request("recipe-diet", params={"diet": diet_type, "limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
    def get_meal_plan_template(self, plan_type: str) -> Dict[str, Any]:
        """Get pre-made meal plan templates"""
        return self._make_request("meal-plan", params={"type": plan_type})
    
    def search_by_flavor(self, flavor: str, limit: int = 50) -> List[Dict]:
        """Search recipes by flavor profile"""
        result = self._make_request(f"ingredients/flavor/{flavor}", params={"limit": limit})
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
    
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
            
        result = self._make_request("recipe2-api/recipe/recipe-day/with-ingredients-categories", params=params)
        return [self._map_to_domain_recipe(r) for r in result] if isinstance(result, list) else []
