
import asyncio
import json
import sys
import os

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.recipedb_service import RecipeDBService

async def debug_mapping():
    print("Initializing RecipeDBService...")
    try:
        service = RecipeDBService()
        
        print("\n--- Fetching Recipe of the Day (Concise) ---")
        # Direct call to see raw
        raw_response = service._make_request("recipe2-api/recipe/recipeofday")
        
        if isinstance(raw_response, list) and len(raw_response) > 0:
            item = raw_response[0]
            print(f"Item Type: {type(item)}")
            print(f"Raw Keys: {list(item.keys())}")
            
            # Check Ingredients
            ing = item.get("ingredients")
            print(f"Ingredients Type: {type(ing)}")
            if isinstance(ing, str):
                print(f"Ingredients String (first 50): {ing[:50]}")
            elif isinstance(ing, list):
                print(f"Ingredients List len: {len(ing)}")
                print(f"First Ingredient: {ing[0] if ing else 'Empty'}")
            
            # Check Nutrition Raw
            print(f"Calories (raw): {item.get('Calories')}")
            print(f"Energy (kcal) (raw): {item.get('Energy (kcal)')}")
            print(f"Protein (g) (raw): {item.get('Protein (g)')}")
            
            # Test Mapping
            print("\n--- Testing Mapping ---")
            mapped = service._map_to_domain_recipe(item)
            
            # Check critical mapped fields
            print(f"Mapped ID: {mapped.get('id')}")
            print(f"Mapped Name: {mapped.get('name')}")
            print(f"Mapped Calories: {mapped.get('calories')}")
            print(f"Mapped Protein: {mapped['macros'].get('protein')}")
            print(f"Mapped Ingredients Count: {len(mapped['ingredients'])}")
            print(f"First Mapped Ingredient: {mapped['ingredients'][0] if mapped['ingredients'] else 'None'}")
            
        elif isinstance(raw_response, dict):
             print(f"Raw is Dict. Keys: {list(raw_response.keys())}")
             print(f"Snippet: {json.dumps(raw_response, default=str)[:200]}")
        else:
             print(f"Raw response unexpected: {type(raw_response)}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_mapping())
