"""
Sustainability helper functions for carbon footprint and water usage calculations
"""
from typing import List, Dict, Any


# Carbon footprint in kg CO2 per kg of food
CARBON_FACTORS = {
    "beef": 27.0,
    "lamb": 39.2,
    "pork": 12.1,
    "chicken": 6.9,
    "turkey": 10.9,
    "fish": 6.1,
    "salmon": 11.9,
    "tuna": 6.1,
    "shrimp": 26.9,
    "eggs": 4.8,
    "cheese": 13.5,
    "milk": 3.2,
    "yogurt": 2.2,
    "butter": 12.1,
    "tofu": 2.0,
    "beans": 2.0,
    "lentils": 0.9,
    "rice": 2.7,
    "wheat": 1.4,
    "bread": 1.6,
    "pasta": 1.5,
    "vegetables": 2.0,
    "fruits": 1.1,
    "nuts": 2.3,
    "default": 2.0
}

# Water usage in liters per kg of food
WATER_FACTORS = {
    "beef": 15400,
    "lamb": 10400,
    "pork": 6000,
    "chicken": 4300,
    "fish": 3900,
    "eggs": 3300,
    "cheese": 5000,
    "milk": 1000,
    "tofu": 2500,
    "beans": 4000,
    "rice": 2500,
    "wheat": 1800,
    "vegetables": 300,
    "fruits": 900,
    "default": 1000
}


def find_carbon_category(ingredient_name: str) -> str:
    """
    Find the carbon category for an ingredient
    """
    ingredient_lower = ingredient_name.lower()
    
    for category in CARBON_FACTORS.keys():
        if category in ingredient_lower:
            return category
    
    return "default"


def calculate_carbon_footprint(ingredients: List[Dict[str, Any]]) -> float:
    """
    Calculate total carbon footprint for a list of ingredients
    Returns kg CO2
    """
    # API First Architecture
    from backend.services.sustainablefooddb_service import SustainableFoodDBService
    # Instantiate service (BaseAPIService handles caching, so this isn't too expensive)
    service = SustainableFoodDBService()
    
    total_carbon = 0.0
    
    for ingredient in ingredients:
        ingredient_name = ingredient if isinstance(ingredient, str) else ingredient.get("name", "")
        quantity = ingredient.get("quantity", 1.0) if isinstance(ingredient, dict) else 1.0
        unit = ingredient.get("unit", "piece") if isinstance(ingredient, dict) else "piece"
        
        # Estimate weight
        from backend.utils.analytics_helpers import estimate_ingredient_weight_kg
        weight_kg = estimate_ingredient_weight_kg(quantity, unit)
        
        # 1. Try API / Local DB Service
        # Service returns CO2 per kg
        api_cf = service.get_ingredient_carbon_footprint(ingredient_name)
        
        if api_cf > 0:
            total_carbon += weight_kg * api_cf
        else:
            # 2. Heuristic Fallback (Level 3)
            category = find_carbon_category(ingredient_name)
            carbon_factor = CARBON_FACTORS.get(category, CARBON_FACTORS["default"])
            total_carbon += weight_kg * carbon_factor
    
    return total_carbon


def calculate_water_usage(ingredients: List[Dict[str, Any]]) -> float:
    """
    Calculate total water usage for a list of ingredients
    Returns liters
    """
    total_water = 0.0
    
    for ingredient in ingredients:
        ingredient_name = ingredient if isinstance(ingredient, str) else ingredient.get("name", "")
        quantity = ingredient.get("quantity", 1.0) if isinstance(ingredient, dict) else 1.0
        unit = ingredient.get("unit", "piece") if isinstance(ingredient, dict) else "piece"
        
        # Find water factor
        category = find_carbon_category(ingredient_name)  # Same categories
        water_factor = WATER_FACTORS.get(category, WATER_FACTORS["default"])
        
        # Estimate weight
        from backend.utils.analytics_helpers import estimate_ingredient_weight_kg
        weight_kg = estimate_ingredient_weight_kg(quantity, unit)
        
        # Calculate water
        total_water += weight_kg * water_factor
    
    return total_water


def calculate_sustainability_metrics(meal_plan_days: List[Dict]) -> Dict[str, Any]:
    """
    Calculate sustainability metrics from meal plan
    """
    if not meal_plan_days:
        return {
            "carbon_saved_kg": 0,
            "water_saved_l": 0,
            "trees_planted_equivalent": 0,
            "sustainable_meals_count": 0
        }
    
    total_carbon = 0.0
    total_water = 0.0
    sustainable_count = 0
    total_meals = 0
    
    SUSTAINABLE_THRESHOLD = 3.0  # kg CO2 per meal
    
    for day in meal_plan_days:
        if "meals" in day:
            for meal in day["meals"].values():
                total_meals += 1
                ingredients = meal.get("ingredients", [])
                
                # Calculate carbon for this meal
                meal_carbon = calculate_carbon_footprint(ingredients)
                total_carbon += meal_carbon
                
                # Calculate water for this meal
                meal_water = calculate_water_usage(ingredients)
                total_water += meal_water
                
                # Check if sustainable
                if meal_carbon < SUSTAINABLE_THRESHOLD:
                    sustainable_count += 1
    
    # Compare to average diet (2.5 kg CO2 per meal)
    average_carbon = total_meals * 2.5
    carbon_saved = max(0, average_carbon - total_carbon)
    
    # Compare to average water usage (3000L per meal)
    average_water = total_meals * 3000
    water_saved = max(0, average_water - total_water)
    
    return {
        "carbon_saved_kg": round(carbon_saved, 1),
        "water_saved_l": round(water_saved, 0),
        "trees_planted_equivalent": round(carbon_saved / 6, 0),  # 1 tree absorbs ~6kg CO2/year
        "sustainable_meals_count": sustainable_count,
        "total_carbon_kg": round(total_carbon, 1),
        "total_water_l": round(total_water, 0)
    }


def calculate_carbon_breakdown(meal_plan_days: List[Dict]) -> List[Dict[str, Any]]:
    """
    Calculate carbon footprint breakdown by food category
    """
    category_carbon = {
        "Meat": 0.0,
        "Dairy": 0.0,
        "Produce": 0.0,
        "Grains": 0.0
    }
    
    for day in meal_plan_days:
        if "meals" in day:
            for meal in day["meals"].values():
                ingredients = meal.get("ingredients", [])
                
                for ingredient in ingredients:
                    ingredient_name = ingredient if isinstance(ingredient, str) else ingredient.get("name", "")
                    quantity = ingredient.get("quantity", 1.0) if isinstance(ingredient, dict) else 1.0
                    unit = ingredient.get("unit", "piece") if isinstance(ingredient, dict) else "piece"
                    
                    # Classify and calculate
                    from backend.utils.analytics_helpers import estimate_ingredient_weight_kg, classify_food_group
                    
                    food_group = classify_food_group(ingredient_name)
                    carbon_category = find_carbon_category(ingredient_name)
                    carbon_factor = CARBON_FACTORS.get(carbon_category, CARBON_FACTORS["default"])
                    weight_kg = estimate_ingredient_weight_kg(quantity, unit)
                    carbon = weight_kg * carbon_factor
                    
                    # Map to breakdown categories
                    if food_group == "Proteins":
                        category_carbon["Meat"] += carbon
                    elif food_group == "Dairy":
                        category_carbon["Dairy"] += carbon
                    elif food_group in ["Vegetables", "Fruits"]:
                        category_carbon["Produce"] += carbon
                    elif food_group == "Grains":
                        category_carbon["Grains"] += carbon
    
    return [
        {"category": cat, "value": round(val, 1)}
        for cat, val in category_carbon.items()
        if val > 0
    ]
