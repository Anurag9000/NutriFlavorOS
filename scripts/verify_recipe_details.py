
import sys
import os
import asyncio
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env variables explicitly BEFORE importing backend modules
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env")
load_dotenv(env_path, override=True)

from backend.services.recipedb_service import RecipeDBService
from backend.config import APIConfig

async def verify_details():
    print(f"DEBUG: APIConfig.RECIPEDB_BASE_URL = '{APIConfig.RECIPEDB_BASE_URL}'")
    service = RecipeDBService()
    print("--- Getting Reference ID ---")
    daily = service.get_recipe_of_day()
    if isinstance(daily, list): daily = daily[0]
    
    # Get ID from mapped domain object (since get_recipe_of_day uses recipesinfo which is now mapped? 
    # Wait, get_recipe_of_day calls _make_request directly, so it returns RAW or whatever the endpoint returns.
    # Actually get_recipe_of_day calls _make_request("recipe2-api/recipe/recipeofday")
    # This likely returns a single dict or list of dicts.
    # The previous debug script showed it returned a dict with 'recipe' key? No, it showed keys like 'recipe_id'.
    
    # Let's just use what we get.
    ref_id = daily.get("recipe_id") or daily.get("id")
    print(f"Ref ID: {ref_id}")
    print(f"Title: {daily.get('recipe_title')}")
    
    if not ref_id:
        print("No ID found. Exiting.")
        return

    print("\n--- Testing get_recipe_info ---")
    info = service.get_recipe_info(str(ref_id))
    print(f"Info Type: {type(info)}")
    if info:
        print(f"Info Keys: {list(info.keys())}")
        print(f"Name: {info.get('name')}")
        print(f"Instructions type: {type(info.get('instructions'))}")

    print("\n--- Testing get_nutrition_info ---")
    nutri = service.get_nutrition_info(str(ref_id))
    print(f"Nutri Type: {type(nutri)}")
    print(f"Nutri Keys: {list(nutri.keys())[:5]}...")

    print("\n--- Testing get_micronutrition_info ---")
    micro = service.get_micronutrition_info(str(ref_id))
    print(f"Micro Type: {type(micro)}")
    print(f"Micro Keys: {list(micro.keys())[:5]}...")

    print("\n--- Testing get_recipe_instructions ---")
    instr = service.get_recipe_instructions(str(ref_id))
    print(f"Instr Type: {type(instr)}")
    print(f"Instr Count: {len(instr)}")

if __name__ == "__main__":
    asyncio.run(verify_details())
