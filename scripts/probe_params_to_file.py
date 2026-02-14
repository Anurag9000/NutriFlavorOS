import requests
import sys

base = "http://cosylab.iiitd.edu.in:6969/flavordb"
key = "TLNUWswde-lnhjdXH-ljLuiN3ll8Y-fYrncXcTatqSnM1ibf"
headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}

with open("probe_clean_output.txt", "w", encoding="utf-8") as f:
    def probe(url, name):
        try:
            f.write(f"Testing {name}...\n")
            resp = requests.get(url, headers=headers, timeout=5, verify=False)
            f.write(f"Status: {resp.status_code}\n")
            if resp.status_code != 200:
                 f.write(f"Body: {resp.text}\n")
            else:
                 f.write("Success!\n")
        except Exception as e:
            f.write(f"Error: {e}\n")

    # 1. Garlic entity search
    probe(f"{base}/entities/by-entity-alias-readable?aliasReadable=Garlic", "Entity_Original")
    probe(f"{base}/entities/by-entity-alias-readable?alias_readable=Garlic", "Entity_Snake")

    # 2. Synthesis
    probe(f"{base}/properties/synthesis?ing1=vanillin&ing2=guaiacol", "Synthesis_Original")
    probe(f"{base}/properties/synthesis?ingredient_1=vanillin&ingredient_2=guaiacol", "Synthesis_Snake")
    probe(f"{base}/properties/synthesis?ingredient1=vanillin&ingredient2=guaiacol", "Synthesis_Snake2")


    # 3. Food Pairing
    probe(f"{base}/food/by-alias?food_pair=Garlic", "Food_Pairing_Original")
