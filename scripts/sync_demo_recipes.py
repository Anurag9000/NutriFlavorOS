import json
import os
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO_DATA_PATH = os.path.join(BASE_DIR, "backend", "data", "demo_data.json")
RECIPES_PATH = os.path.join(BASE_DIR, "backend", "data", "recipes.json")

def sync_recipes():
    print(f"Reading demo data from {DEMO_DATA_PATH}...")
    try:
        with open(DEMO_DATA_PATH, 'r') as f:
            demo_data = json.load(f)
    except FileNotFoundError:
        print("Demo data file not found!")
        return

    print(f"Reading recipes from {RECIPES_PATH}...")
    try:
        with open(RECIPES_PATH, 'r') as f:
            recipes = json.load(f)
    except FileNotFoundError:
        print("Recipes file not found! Creating new list.")
        recipes = []

    # Create a set of existing IDs for fast lookup
    existing_ids = set()
    for r in recipes:
        if "Recipe_id" in r:
            existing_ids.add(str(r["Recipe_id"]))
        if "_id" in r:
            existing_ids.add(str(r["_id"]))

    new_recipes_count = 0
    days = demo_data.get("meal_plan", {}).get("days", [])
    
    for day in days:
        meals = day.get("meals", {})
        for meal_type, meal in meals.items():
            meal_id = str(meal.get("id"))
            
            if meal_id and meal_id not in existing_ids:
                print(f"Adding missing recipe: {meal.get('name')} ({meal_id})")
                
                # key 'ingredients' in demo_data is a list of strings
                # recipes.json doesn't strictly enforce ingredients structure in the flat list shown previously,
                # but let's try to be consistent.
                
                new_recipe = {
                    "_id": meal_id,
                    "Recipe_id": meal_id,
                    "Recipe_title": meal.get("name"),
                    "Calories": str(meal.get("calories", 0)),
                    "cook_time": "15", # Default
                    "prep_time": "15", # Default
                    "total_time": "30",
                    "servings": "1",
                    "Region": "Global",
                    "Sub_region": "Demo",
                    "Continent": "Global",
                    "Source": "FoodScope Demo",
                    "Carbohydrate, by difference (g)": str(meal.get("macros", {}).get("carbs", 0)),
                    "Energy (kcal)": str(meal.get("calories", 0)),
                    "Protein (g)": str(meal.get("macros", {}).get("protein", 0)),
                    "Total lipid (fat) (g)": str(meal.get("macros", {}).get("fat", 0)),
                    "Utensils": "bowl",
                    "Processes": "cook",
                    "vegan": "0.0",
                    "pescetarian": "0.0",
                    "ovo_vegetarian": "0.0",
                    "lacto_vegetarian": "0.0",
                    "ovo_lacto_vegetarian": "0.0",
                    "readyInMinutes": 30,
                    "healthScore": 90,
                    "image_url": meal.get("image_url", "")
                }
                
                recipes.append(new_recipe)
                existing_ids.add(meal_id)
                new_recipes_count += 1

    if new_recipes_count > 0:
        print(f"Saving {new_recipes_count} new recipes to {RECIPES_PATH}...")
        with open(RECIPES_PATH, 'w') as f:
            json.dump(recipes, f, indent=2)
        print("Done!")
    else:
        print("No new recipes to add.")

if __name__ == "__main__":
    sync_recipes()
