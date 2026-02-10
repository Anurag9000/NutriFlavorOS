import os
import sys
import json
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force Mock Mode
os.environ["MOCK_MODE"] = "true"
os.environ["CACHE_ENABLED"] = "false" # Disable cache to test fresh fetches

from backend.config import APIConfig
from backend.services.recipedb_service import RecipeDBService
from backend.services.flavordb_service import FlavorDBService
from backend.services.dietrxdb_service import DietRxDBService
from backend.services.sustainablefooddb_service import SustainableFoodDBService

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Verifier")

def check(condition, message):
    if condition:
        logger.info(f"✅ {message}")
    else:
        logger.error(f"❌ {message}")
        raise AssertionError(message)

def verify_datasets_integrity():
    logger.info("\n📊 Verifying Dataset Integrity (Rows & Columns)...")
    
    # 1. Recipes Dictionary compliance
    with open(APIConfig.MOCK_RECIPES_FILE, 'r') as f:
        recipes = json.load(f)
    
    check(len(recipes) >= 50, f"Recipes dataset has {len(recipes)} items (Target: 50+)")
    
    required_recipe_fields = [
        "id", "title", "readyInMinutes", "servings", "image", "cuisines", 
        "diets", "instructions", "nutrition", "micronutrients", "ingredients", "aggregatedFlavorProfile"
    ]
    
    for r in recipes:
        missing = [field for field in required_recipe_fields if field not in r]
        check(not missing, f"Recipe {r['id']} missing fields: {missing}")
        check(isinstance(r["nutrition"], dict), f"Recipe {r['id']} nutrition is valid dict")
        check(len(r["ingredients"]) > 0, f"Recipe {r['id']} has ingredients")

    # 2. FlavorDB compliance
    with open(APIConfig.MOCK_FLAVOR_DB_FILE, 'r') as f:
        flavors = json.load(f)
        
    required_flavor_fields = [
        "ingredient", "category", "flavor_vector", "functional_groups", 
        "aroma_threshold", "taste_threshold", "molecular_properties", "safety_approvals"
    ]
    
    for name, item in flavors.items():
        missing = [field for field in required_flavor_fields if field not in item]
        check(not missing, f"Ingredient '{name}' missing fields: {missing}")
        check(len(item["flavor_vector"]) > 0, f"Ingredient '{name}' has flavor vector")

    # 3. DietRx compliance
    with open(APIConfig.MOCK_DIET_RX_FILE, 'r') as f:
        dietrx = json.load(f)
    
    check("diseases" in dietrx, "DietRx has 'diseases' key")
    check("interactions" in dietrx, "DietRx has 'interactions' key")
    
    for d_name, d_info in dietrx["diseases"].items():
        check("beneficial_foods" in d_info, f"Disease '{d_name}' has beneficial_foods")
        check("harmful_foods" in d_info, f"Disease '{d_name}' has harmful_foods")

    # 4. SustainableDB compliance
    with open(APIConfig.MOCK_SUSTAINABLE_DB_FILE, 'r') as f:
        susdb = json.load(f)
        
    for name, item in susdb.items():
        check("carbon_footprint_kg" in item, f"Sustainable '{name}' has carbon footprint")


def verify_service_integration():
    logger.info("\n🔗 Verifying Service Layer Integration (API Fallback)...")
    
    # --- RecipeDB Service ---
    r_service = RecipeDBService()
    
    # Test Get Info
    r1 = r_service.get_recipe_info("1")
    check(r1.get("id") == "1", "RecipeDB: get_recipe_info('1') working")
    
    # Test Nutrition
    nut = r_service.get_nutrition_info("1")
    check("calories" in nut, "RecipeDB: get_nutrition_info('1') working")
    
    # Test Instructions
    instr = r_service.get_recipe_instructions("1")
    check(len(instr) > 0, "RecipeDB: get_recipe_instructions('1') working")
    
    # Test Search by Cuisine
    asian = r_service.search_by_cuisine("Asian")
    check(len(asian) > 0, f"RecipeDB: search_by_cuisine('Asian') returned {len(asian)} items")
    
    # Test Search by Calories (Range)
    cal_res = r_service.search_by_calories(200, 500)
    check(len(cal_res) > 0, "RecipeDB: search_by_calories(200, 500) working")
    
    # Test Search by Title
    title_res = r_service.search_by_title("Chicken")
    check(len(title_res) > 0, "RecipeDB: search_by_title('Chicken') working")
    
    # --- FlavorDB Service ---
    f_service = FlavorDBService()
    
    # Test Profile
    prof = f_service.get_flavor_profile("chicken breast")
    check(len(prof.get("flavor_vector", {})) > 0, "FlavorDB: get_flavor_profile('chicken breast') working")
    
    # Test Functional Groups
    fg = f_service.get_functional_groups("chicken breast")
    check(isinstance(fg, list), "FlavorDB: get_functional_groups('chicken breast') working")
    
    # Test Molecular Properties
    mol = f_service.get_molecular_properties("chicken breast")
    check("weight" in mol, "FlavorDB: get_molecular_properties('chicken breast') working")
    
    # Test Safety
    safe = f_service.check_safety_approval("chicken breast")
    check(safe.get("fema") is True, "FlavorDB: check_safety_approval working")

    # --- DietRxDB Service ---
    d_service = DietRxDBService()
    
    dis = d_service.get_disease_info("Diabetes Type 2")
    check(dis.get("name") == "Diabetes Type 2", "DietRxDB: get_disease_info working")
    
    # --- SustainableFoodDB Service ---
    s_service = SustainableFoodDBService()
    
    cf = s_service.get_ingredient_carbon_footprint("beef steak")
    check(cf > 0, "SustainableDB: get_ingredient_carbon_footprint('beef steak') working")
    
    total = s_service.calculate_meal_carbon_sum(["beef steak", "potato"])
    check(total > 0, "SustainableDB: calculate_meal_carbon_sum working")


if __name__ == "__main__":
    try:
        verify_datasets_integrity()
        verify_service_integration()
        print("\n✨ ALL CHECKS PASSED SUCCESSFULLY! ✨")
    except Exception as e:
        print(f"\n❌ VERIFICATION FAILED: {str(e)}")
        sys.exit(1)
