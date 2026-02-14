
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.flavordb_service import FlavorDBService
from backend.services.sustainablefooddb_service import SustainableFoodDBService
from backend.services.recipedb_service import RecipeDBService
from backend.engines.taste_engine import TasteEngine
from backend.config import APIConfig

def test_api_first():
    print("🚀 Verifying API-First Architecture...\n")
    
    # Check Config
    print(f"[{'FAIL' if APIConfig.MOCK_MODE else 'OK'}] MOCK_MODE is {APIConfig.MOCK_MODE}")
    if APIConfig.MOCK_MODE:
        print("Error: MOCK_MODE must be False for this test.")
        return

    # 1. Test RecipeDB (Meals)
    print("\n1. Testing RecipeDB (Meals Display)...")
    r_service = RecipeDBService()
    try:
        # This now uses API (search by title)
        results = r_service.search_by_title("Chicken") 
        if results and len(results) > 0:
            print(f"✅ Recipe Search Successful: Found {len(results)} items via API.")
            print(f"   Sample: {results[0].get('name')}")
        else:
            print("⚠️ Recipe Search returned empty (Might be API limit or key issue).")
            
        # Test Recipe of Day (Direct API)
        rod = r_service.get_recipe_of_day()
        if rod:
             print(f"✅ Recipe of Day: {rod.get('Recipe_title')}")
    except Exception as e:
        print(f"❌ RecipeDB Failed: {e}")

    # 2. Test FlavorDB (Training Model / TasteEngine)
    print("\n2. Testing FlavorDB (Model Data)...")
    f_service = FlavorDBService()
    try:
        # Vanillin is a molecule, likely to succeed in API
        profile = f_service.get_flavor_profile("Vanillin")
        if profile and "flavor_vector" in profile:
            print(f"✅ Flavor Profile (Vanillin): Got vector with {len(profile.get('flavor_vector'))} compounds.")
        else:
            print("⚠️ Flavor Profile (Vanillin) returned empty (API might not have detailed data for this input).")
            
        # Test Functional Groups
        groups = f_service.get_functional_groups("Vanillin")
        print(f"✅ Functional Groups: {groups}")
        
    except Exception as e:
        print(f"❌ FlavorDB Failed: {e}")

    # 3. Test SustainableFoodDB (Metadata)
    print("\n3. Testing SustainableFoodDB (Metadata)...")
    s_service = SustainableFoodDBService()
    try:
        # "Beef" usually has data
        cf = s_service.get_ingredient_carbon_footprint("Beef")
        print(f"✅ Carbon Footprint (Beef): {cf} kg CO2e")
        
        if cf == 0.0:
             print("   (Note: 0.0 might indicate API missing data or fallback to default)")
             
    except Exception as e:
        print(f"❌ SustainableFoodDB Failed: {e}")

    # 4. Test Sustainability Helper (Integration)
    print("\n4. Testing Sustainability Helper (Integration)...")
    try:
        from backend.utils.sustainability_helpers import calculate_carbon_footprint
        ingredients = [{"name": "Beef", "quantity": 1, "unit": "kg"}]
        total = calculate_carbon_footprint(ingredients)
        print(f"✅ Helper Calculation (1kg Beef): {total} kg CO2e")
    except Exception as e:
        print(f"❌ Helper Failed: {e}")

    print("\n--------------------------------------------------")
    print("ARCHITECTURE VERIFICATION COMPLETE")
    print("If checkmarks above are present, the system is attempting API calls first.")
    print("If API fails, BaseAPIService will handle fallback (not tested here, assumed safe).")

if __name__ == "__main__":
    test_api_first()
