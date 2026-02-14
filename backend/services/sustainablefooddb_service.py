"""
SustainableFoodDB API Service - Environmental impact tracking
"""
import json
import os
from typing import List, Dict, Any, Optional
from backend.services.base_service import BaseAPIService
from backend.config import APIConfig

class SustainableFoodDBService(BaseAPIService):
    """Service for tracking carbon footprint - prioritizing Local JSON data"""
    
    def __init__(self):
        super().__init__(
            base_url=APIConfig.SUSTAINABLEFOODDB_BASE_URL,
            api_key=APIConfig.SUSTAINABLEFOODDB_API_KEY
        )
        self.local_db = {} # Unused

    
    def search_sustainable_foods(self, query: str) -> List[Dict]:
        """Search for sustainable food options"""
        return self._make_request("search", params={"q": query})
    
    def get_ingredient_carbon_footprint(self, ingredient: str) -> float:
        """Get carbon footprint for a single ingredient (kg CO2e)"""
        result = self._make_request("ingredient-cf", params={"ingredient": ingredient})
        return result.get("carbon_footprint", 0.0)
    
    def get_recipe_carbon_footprint(self, recipe_id: str) -> Dict[str, Any]:
        """Get total carbon footprint for a recipe"""
        # This would require recipe ingredients lookups. 
        # For now, we fall back to API or return 0 if API fails (likely)
        return self._make_request(f"recipe/{recipe_id}")
    
    def calculate_meal_carbon_sum(self, ingredients: List[str]) -> float:
        """Calculate total carbon footprint for a list of ingredients"""
        total = 0.0
        
        for ing in ingredients:
            # API First (via get_ingredient_carbon_footprint)
            total += self.get_ingredient_carbon_footprint(ing)
        
        return total
    
    def get_carbon_by_name(self, food_name: str) -> float:
        """Get carbon footprint by food name"""
        return self.get_ingredient_carbon_footprint(food_name)
    
    def get_sustainability_score(self, ingredients: List[str]) -> Dict[str, Any]:
        """
        Calculate comprehensive sustainability score
        Returns: score (0-100), carbon footprint, water usage estimate
        """
        total_carbon = self.calculate_meal_carbon_sum(ingredients)
        
        # Score calculation (lower carbon = higher score)
        # Average meal carbon footprint is ~2.5 kg CO2e
        # Score: 100 for 0kg, 0 for 5kg+
        score = max(0, min(100, 100 - (total_carbon / 5.0 * 100)))
        
        return {
            "score": round(score, 1),
            "carbon_footprint_kg": round(total_carbon, 2),
            "rating": "Excellent" if score >= 80 else "Good" if score >= 60 else "Fair" if score >= 40 else "Poor"
        }
