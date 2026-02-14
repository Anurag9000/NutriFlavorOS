import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def test_url(name, url, expected_status=[200, 404]):
    print(f"Testing {name}: {url} ...", end=" ")
    try:
        resp = requests.get(url, verify=False, timeout=5)
        print(f"[{resp.status_code}]")
        if resp.status_code == 200:
            try:
                data = resp.json()
                keys = list(data.keys()) if isinstance(data, dict) else "LIST"
                print(f"  > Valid JSON. Keys: {str(keys)[:50]}")
                return True
            except:
                print("  > Not JSON")
    except Exception as e:
        print(f"FAILED: {str(e)[:50]}")
    return False

# 1. RecipeDB (Known: http://cosylab.iiitd.edu.in:6969)
test_url("RecipeDB (Ref)", "http://cosylab.iiitd.edu.in:6969/recipe2-api/recipe/recipeofday")

# 2. FlavorDB (Known: http://cosylab.iiitd.edu.in:6969/flavordb)
test_url("FlavorDB (Ref)", "http://cosylab.iiitd.edu.in:6969/flavordb/entities/by-entity-alias-readable?entity_alias_readable=Garlic")

# 3. SustainableDB Information Gathering
# Trying variants
base_sust = "http://cosylab.iiitd.edu.in:6969/sustainablefooddb"
test_url("Sustainable (Port 6969)", f"{base_sust}/search?q=apple")
test_url("Sustainable (Search)", f"{base_sust}/search?q=apple")
test_url("Sustainable (Ingredient)", f"{base_sust}/ingredient-cf?ingredient=apple")

# 4. DietRxDB Information Gathering
# Config says https://cosylab.iiitd.edu.in/dietrxdb/
# Postman for DietRx? (Don't have one loaded, inferring)
base_diet = "https://cosylab.iiitd.edu.in/dietrxdb"
base_diet_6969 = "http://cosylab.iiitd.edu.in:6969/dietrxdb"

test_url("DietRx (HTTPS)", f"{base_diet}/disease/flu")
test_url("DietRx (Port 6969)", f"{base_diet_6969}/disease/flu")
test_url("DietRx (Port 6969 - all)", f"{base_diet_6969}/all-details")
