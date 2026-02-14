import requests
import json
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def check(name, url):
    print(f"--- Checking {name} ---")
    print(f"URL: {url}")
    try:
        resp = requests.get(url, verify=False, timeout=5)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print("Content Snippet:", resp.text[:100])
        else:
            print("Response:", resp.text[:100])
    except Exception as e:
        print(f"Error: {e}")
    print("\n")

# Sustainable
base_sust = "http://cosylab.iiitd.edu.in:6969/sustainablefooddb"
check("Sustainable Search", f"{base_sust}/search?q=apple")
check("Sustainable Ingredient", f"{base_sust}/ingredient-cf?ingredient=apple")

# DietRx
base_diet = "http://cosylab.iiitd.edu.in:6969/dietrxdb"
check("DietRx All Diseases", f"{base_diet}/all-details")
check("DietRx Disease Info", f"{base_diet}/disease/Flu")
