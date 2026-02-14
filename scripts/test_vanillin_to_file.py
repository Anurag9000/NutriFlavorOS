import requests
import sys

base = "http://cosylab.iiitd.edu.in:6969/flavordb"
key = "TLNUWswde-lnhjdXH-ljLuiN3ll8Y-fYrncXcTatqSnM1ibf"
headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}
url = f"{base}/molecules_data/by-commonName?commonName=vanillin"

try:
    print("Testing...", flush=True)
    resp = requests.get(url, headers=headers, timeout=5, verify=False)
    print(f"Status: {resp.status_code}", flush=True)
    with open("test_output.txt", "w", encoding="utf-8") as f:
        f.write(resp.text)
    print("Written to test_output.txt")
except Exception as e:
    print(f"Error: {e}", flush=True)
