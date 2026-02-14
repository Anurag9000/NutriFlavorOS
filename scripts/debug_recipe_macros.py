
import sys
import os
import json
import codecs

# Force UTF-8 for stdout
sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.recipedb_service import RecipeDBService

def debug_macros():
    service = RecipeDBService()
    recipes = service.get_all_recipes()
    
    targets = ["Best Bobotie", "Moroccan Chicken Tagine", "Magpie's Easy Falafel Cakes"]
    
    print(f"Loaded {len(recipes)} recipes.")
    
    for r in recipes:
        if any(t in r["name"] for t in targets):
            print(f"\n--- {r['name']} ---")
            print(f"Calories: {r['calories']}")
            print(f"Protein: {r['macros']['protein']}g")
            print(f"Fat: {r['macros']['fat']}g")
            print(f"Carbs: {r['macros']['carbs']}g")
            
            # Sanity check
            cals_from_macros = (r['macros']['protein'] * 4) + (r['macros']['fat'] * 9) + (r['macros']['carbs'] * 4)
            print(f"Calculated Cals from Macros: {cals_from_macros}")
            
            if abs(cals_from_macros - r['calories']) > 50:
                print("⚠️  Mismatch > 50 cal")
            else:
                print("✅  Consistent")

if __name__ == "__main__":
    debug_macros()
