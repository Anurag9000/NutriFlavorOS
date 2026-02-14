"""
Analytics helper functions for calculating real metrics from meal plans
"""
from typing import List, Dict, Any
from backend.models import DailyPlan, Recipe


def classify_food_group(ingredient_name: str) -> str:
    """
    Classify ingredient into food group
    """
    ingredient_lower = ingredient_name.lower()
    
    vegetables = ["lettuce", "tomato", "carrot", "broccoli", "spinach", "kale", 
                  "cucumber", "pepper", "onion", "garlic", "celery", "cabbage",
                  "cauliflower", "zucchini", "eggplant", "mushroom", "asparagus"]
    
    fruits = ["apple", "banana", "orange", "berry", "strawberry", "blueberry",
              "grape", "mango", "pineapple", "watermelon", "peach", "pear",
              "cherry", "lemon", "lime", "avocado"]
    
    grains = ["rice", "wheat", "oat", "quinoa", "barley", "bread", "pasta",
              "cereal", "flour", "corn", "tortilla", "noodle", "couscous"]
    
    proteins = ["chicken", "beef", "pork", "fish", "salmon", "tuna", "tofu",
                "egg", "turkey", "lamb", "shrimp", "beans", "lentil", "chickpea",
                "tempeh", "seitan"]
    
    dairy = ["milk", "cheese", "yogurt", "butter", "cream", "cheddar", "mozzarella",
             "parmesan", "feta", "cottage cheese", "sour cream"]
    
    if any(veg in ingredient_lower for veg in vegetables):
        return "Vegetables"
    elif any(fruit in ingredient_lower for fruit in fruits):
        return "Fruits"
    elif any(grain in ingredient_lower for grain in grains):
        return "Grains"
    elif any(protein in ingredient_lower for protein in proteins):
        return "Proteins"
    elif any(d in ingredient_lower for d in dairy):
        return "Dairy"
    else:
        return "Other"


def calculate_daily_health_score(day_meals: Dict[str, Any], user_target_calories: int = 2000) -> int:
    """
    Calculate health score for a day based on meals
    Returns score 0-100
    """
    if not day_meals:
        return 0
    
    # Calculate total calories
    total_calories = sum(meal.get("calories", 0) for meal in day_meals.values())
    
    # Calculate total macros
    total_protein = sum(meal.get("macros", {}).get("protein", 0) for meal in day_meals.values())
    total_carbs = sum(meal.get("macros", {}).get("carbs", 0) for meal in day_meals.values())
    total_fat = sum(meal.get("macros", {}).get("fat", 0) for meal in day_meals.values())
    
    # Score component 1: Calorie target match (0-100)
    if total_calories == 0:
        calorie_score = 0
    else:
        calorie_diff_pct = abs(total_calories - user_target_calories) / user_target_calories
        calorie_score = max(0, 100 - (calorie_diff_pct * 100))
    
    # Score component 2: Macro balance (0-100)
    # Ideal: 30% protein, 40% carbs, 30% fat (in calories)
    total_macro_calories = (total_protein * 4) + (total_carbs * 4) + (total_fat * 9)
    if total_macro_calories == 0:
        macro_score = 0
    else:
        protein_pct = (total_protein * 4) / total_macro_calories * 100
        carbs_pct = (total_carbs * 4) / total_macro_calories * 100
        fat_pct = (total_fat * 9) / total_macro_calories * 100
        
        # Calculate deviation from ideal
        protein_dev = abs(protein_pct - 30)
        carbs_dev = abs(carbs_pct - 40)
        fat_dev = abs(fat_pct - 30)
        
        avg_deviation = (protein_dev + carbs_dev + fat_dev) / 3
        macro_score = max(0, 100 - avg_deviation)
    
    # Score component 3: Meal count (0-100)
    meal_count = len(day_meals)
    meal_score = min(100, (meal_count / 3) * 100)  # 3 meals = 100%
    
    # Weighted average
    overall_score = (calorie_score * 0.4 + macro_score * 0.4 + meal_score * 0.2)
    
    return int(overall_score)


def calculate_variety_distribution(meal_plan_days: List[Dict]) -> List[Dict[str, Any]]:
    """
    Calculate food group distribution from meal plan
    Returns list of {name, value} for pie chart
    """
    if not meal_plan_days:
        return []
    
    food_group_counts = {
        "Vegetables": 0,
        "Fruits": 0,
        "Grains": 0,
        "Proteins": 0,
        "Dairy": 0,
        "Other": 0
    }
    
    # Count ingredients by food group
    for day in meal_plan_days:
        if "meals" in day:
            for meal in day["meals"].values():
                # Get ingredients from meal
                ingredients = meal.get("ingredients", [])
                for ingredient in ingredients:
                    ingredient_name = ingredient if isinstance(ingredient, str) else ingredient.get("name", "")
                    group = classify_food_group(ingredient_name)
                    food_group_counts[group] += 1
    
    # Convert to percentages
    total = sum(food_group_counts.values())
    if total == 0:
        return []
    
    result = []
    for group, count in food_group_counts.items():
        if count > 0:  # Only include groups with items
            result.append({
                "name": group,
                "value": round((count / total) * 100)
            })
    
    return result


def estimate_ingredient_weight_kg(quantity: float, unit: str) -> float:
    """
    Estimate weight in kg from quantity and unit
    """
    # Conversion factors to kg
    conversions = {
        "kg": 1.0,
        "g": 0.001,
        "lb": 0.453592,
        "oz": 0.0283495,
        "cup": 0.24,  # Average
        "tbsp": 0.015,
        "tsp": 0.005,
        "piece": 0.15,  # Average piece
        "item": 0.15,
        "whole": 0.2,
    }
    
    unit_lower = unit.lower()
    factor = conversions.get(unit_lower, 0.1)  # Default 100g
    
    return quantity * factor
