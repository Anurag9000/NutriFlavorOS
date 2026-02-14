import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base = "http://cosylab.iiitd.edu.in:6969/flavordb"
key = "TLNUWswde-lnhjdXH-ljLuiN3ll8Y-fYrncXcTatqSnM1ibf"
headers = {"Authorization": f"Bearer {key}"}

# 1. Fetch Entity (Garlic)
url = f"{base}/entities/by-entity-alias-readable?entity_alias_readable=Garlic"
print(f"Fetching: {url}")
try:
    resp = requests.get(url, headers=headers, verify=False, timeout=10)
    data = resp.json()
    
    # Analyze structure
    print("\n--- ENTITY STRUCTURE ---")
    if isinstance(data, list):
        print("Root is LIST")
        if data:
            item = data[0]
            print(f"Keys in first item: {list(item.keys())}")
            # Check for nested complex fields
            for k, v in item.items():
                if isinstance(v, (dict, list)):
                    print(f"Key '{k}' is {type(v).__name__} with len {len(v) if hasattr(v, '__len__') else 'N/A'}")
    elif isinstance(data, dict):
         print(f"Root is DICT. Keys: {list(data.keys())}")
         # Check standard wrapper
         if "items" in data:
             print("Found 'items' key.")
         if "content" in data:
              print(f"Found 'content' key. content keys: {list(data['content'][0].keys()) if data['content'] else 'Empty'}")

    
    # 2. Fetch Molecule (Vanillin) to see what IT has
    url2 = f"{base}/molecules_data/by-commonName?common_name=vanillin"
    print(f"\nFetching Molecule: {url2}")
    resp2 = requests.get(url2, headers=headers, verify=False, timeout=10)
    data2 = resp2.json()
    print("\n--- MOLECULE STRUCTURE ---")
    if "content" in data2 and data2["content"]:
        mol = data2["content"][0]
        print(f"Molecule Keys: {list(mol.keys())}")
    else:
        print(f"Unexpected molecule structure: {data2.keys() if isinstance(data2, dict) else type(data2)}")

except Exception as e:
    print(f"Error: {e}")
