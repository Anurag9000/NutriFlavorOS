import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base = "http://cosylab.iiitd.edu.in:6969/flavordb"
key = "TLNUWswde-lnhjdXH-ljLuiN3ll8Y-fYrncXcTatqSnM1ibf"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

urls = [
    f"{base}/molecules_data/by-commonName?commonName=vanillin",
    f"{base}/entities/by-entity-alias-readable?aliasReadable=Garlic",
    f"{base}/food/by-alias?food_pair=Garlic",
    f"{base}/entities/by-name-and-category?name=Garlic&category=Spice" 
]

print("START_AUTH_TEST_V2")
for url in urls:
    try:
        print(f"Testing: {url}")
        resp = requests.get(url, headers=headers, timeout=3, verify=False)
        print(f"Result: {resp.status_code}")
        print(f"Body: {resp.text[:200]}") # Print first 200 chars always
    except Exception as e:
        print(f"ERROR_URL: {url} Msg: {type(e).__name__}")
print("END_AUTH_TEST_V2")
