import requests
import sys

base = "http://cosylab.iiitd.edu.in:6969/flavordb"
key = "TLNUWswde-lnhjdXH-ljLuiN3ll8Y-fYrncXcTatqSnM1ibf"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

def probe(url, name):
    try:
        print(f"Testing {name}...", flush=True)
        resp = requests.get(url, headers=headers, timeout=5, verify=False)
        print(f"Status: {resp.status_code}", flush=True)
        if resp.status_code != 200:
             print(f"Body: {resp.text}", flush=True)
        else:
             print("Success!", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

# 1. Garlic entity search
probe(f"{base}/entities/by-entity-alias-readable?aliasReadable=Garlic", "Entity by Readable (Original)")
probe(f"{base}/entities/by-entity-alias-readable?alias_readable=Garlic", "Entity by Readable (Snake)")

# 2. Synthesis (Molecules likely, but testing params)
probe(f"{base}/properties/synthesis?ing1=vanillin&ing2=guaiacol", "Synthesis (Original)")
probe(f"{base}/properties/synthesis?ingredient_1=vanillin&ingredient_2=guaiacol", "Synthesis (Snake)")

# 3. Food Pairing
probe(f"{base}/food/by-alias?food_pair=Garlic", "Food Pairing (Original)")
# food_pair is already snake_case in Postman, unlike aliasReadable. so maybe it works?
