import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.recipedb_service import RecipeDBService
from backend.services.flavordb_service import FlavorDBService
from backend.services.sustainablefooddb_service import SustainableFoodDBService
from backend.services.dietrxdb_service import DietRxDBService
from backend.engines.taste_engine import TasteEngine
from backend.models import UserProfile
import urllib3

urllib3.disable_warnings()

def check(name, func):
    print(f"\n--- Checking {name} ---")
    try:
        res = func()
        if res:
            print(f"SUCCESS. \nSample: {str(res)[:100]}...")
        else:
            print("WARNING: Empty Result (might be valid if search found nothing)")
    except Exception as e:
        print(f"FAILURE: {e}")

def verify_all():
    print("=== STARTING FULL BACKEND VERIFICATION ===")
    
    # 1. RecipeDB
    r = RecipeDBService()
    check("RecipeDB (Recipe of Day)", lambda: r.get_recipe_of_day())
    
    # 2. FlavorDB
    f = FlavorDBService()
    check("FlavorDB (Entity Search: Garlic)", lambda: f.search_entities_by_readable_name("Garlic"))
    check("FlavorDB (Molecule Search: Vanillin)", lambda: f.get_molecule_details("Vanillin"))
    
    # 3. SustainableDB
    s = SustainableFoodDBService()
    # 'search' endpoint in service uses "search?q=..."
    check("SustainableDB (Search: Apple)", lambda: s.search_sustainable_foods("Apple"))
    
    # 4. DietRxDB
    d = DietRxDBService()
    # 'disease' endpoint
    check("DietRxDB (Disease: Flu)", lambda: d.get_disease_info("Flu"))

    # 5. TasteEngine Integration
    print("\n--- Checking TasteEngine Integration ---")
    try:
        engine = TasteEngine()
        # Mock user with one complex Entity (Garlic - should skip) and one Molecule (Vanillin - should work if name matches common name?)
        # Wait, Vanillin isn't usually in 'liked_ingredients' which are foods. 
        # But this tests the robustness. 
        # If I pass 'Garlic', it should print warning (maybe) and continue.
        user = UserProfile(
            name="test",
            age=30,
            weight_kg=70.0,
            height_cm=170.0,
            gender="male",
            activity_level=1.5,
            goal="maintenance",
            liked_ingredients=["Garlic", "Chocolate"], 
            disliked_ingredients=[]
        )
        print("Running generate_flavor_genome...")
        genome = engine.generate_flavor_genome(user)
        print(f"Resulting Genome Keys: {list(genome.keys())}")
        print("SUCCESS: Engine ran without crashing.")
    except Exception as e:
        print(f"FAILURE: Engine Crashed: {e}")

if __name__ == "__main__":
    verify_all()
