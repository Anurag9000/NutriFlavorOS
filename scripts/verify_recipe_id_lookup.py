
import asyncio
import sys
import os
import json

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.recipedb_service import RecipeDBService

async def verify_id_lookup():
    service = RecipeDBService()
    print("--- Fetching a Reference ID ---")
    
    # Get a valid ID first
    try:
        daily = service.get_recipe_of_day()
        if isinstance(daily, list) and daily:
             daily = daily[0]
        
        ref_id = str(daily.get("recipe_id") or daily.get("Recipe_id") or daily.get("id"))
        ref_title = daily.get("recipe_title") or daily.get("Recipe_title") or daily.get("title")
        
        print(f"Reference ID: {ref_id}")
        print(f"Reference Title: {ref_title}")
        
        if not ref_id:
            print("Could not get a reference ID. Exiting.")
            return

        print("\n--- Testing Lookup by ID ---")
        # Test 1: param 'recipe_id'
        print("Test 1: params={'recipe_id': ref_id}")
        res1 = service._make_request("recipe2-api/recipe/recipesinfo", params={"recipe_id": ref_id})
        print(f"Result Type: {type(res1)}")
        if isinstance(res1, list):
             print(f"Count: {len(res1)}")
             if len(res1) > 0:
                 print(f"Item 0 Keys: {list(res1[0].keys())}")
                 print(f"Item 0 ID values: _id={res1[0].get('_id')}, recipe_id={res1[0].get('recipe_id')}, id={res1[0].get('id')}")
        
        # Test 2: param 'id'
        print("\nTest 2: params={'id': ref_id}")
        res2 = service._make_request("recipe2-api/recipe/recipesinfo", params={"id": ref_id})
        if isinstance(res2, list):
             print(f"Count: {len(res2)}")
             
        # Test 3: param 'q' (generic query)
        print("\nTest 3: params={'q': ref_id}")
        res3 = service._make_request("recipe2-api/recipe/recipesinfo", params={"q": ref_id})
        if isinstance(res3, list):
             print(f"Count: {len(res3)}")

        # Test 4: Direct path (wildcard guess)
        print(f"\nTest 4: path 'recipe2-api/recipe/recipesinfo/{ref_id}'")
        try:
            res4 = service._make_request(f"recipe2-api/recipe/recipesinfo/{ref_id}")
            print("Success (Path param workd)")
            print(json.dumps(res4, default=str)[:200])
        except Exception as e:
            print(f"Failed: {e}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(verify_id_lookup())
