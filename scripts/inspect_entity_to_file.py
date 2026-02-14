import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base = "http://cosylab.iiitd.edu.in:6969/flavordb"
key = "TLNUWswde-lnhjdXH-ljLuiN3ll8Y-fYrncXcTatqSnM1ibf"
headers = {"Authorization": f"Bearer {key}"}

with open("entity_structure_clean.txt", "w", encoding="utf-8") as f:
    def log(msg):
        print(msg)
        f.write(msg + "\n")

    try:
        # 1. Fetch Entity (Garlic)
        url = f"{base}/entities/by-entity-alias-readable?entity_alias_readable=Garlic"
        log(f"Fetching: {url}")
        resp = requests.get(url, headers=headers, verify=False, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, list) and data:
                item = data[0]
                log(f"Entity PURE LIST Item Keys: {list(item.keys())}")
            elif isinstance(data, dict):
                 log(f"Entity Wrapper Keys: {list(data.keys())}")
                 if "content" in data and data["content"]:
                     item = data["content"][0]
                     log(f"Entity CONTENT Item Keys: {list(item.keys())}")
                     # Print sample of complex fields if any
                     if "molecules" in item: log(f"Has 'molecules' field? Yes, len {len(item['molecules'])}")
                 else:
                     log("Entity content is empty or missing")
        else:
            log(f"Entity Fetch Failed: {resp.status_code}")

        # 2. Fetch Molecule (Vanillin)
        url2 = f"{base}/molecules_data/by-commonName?common_name=vanillin"
        log(f"Fetching Molecule: {url2}")
        resp2 = requests.get(url2, headers=headers, verify=False, timeout=10)
        if resp2.status_code == 200:
             data2 = resp2.json()
             if "content" in data2 and data2["content"]:
                 mol = data2["content"][0]
                 log(f"Molecule Keys: {list(mol.keys())}")
    except Exception as e:
        log(f"Error: {e}")
