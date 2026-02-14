import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

base_sust = "http://cosylab.iiitd.edu.in:6969/sustainablefooddb"
base_diet = "http://cosylab.iiitd.edu.in:6969/dietrxdb"
api_key = "TLNUWswde-lnhjdXH-ljLuiN3ll8Y-fYrncXcTatqSnM1ibf"

with open("probe_results_clean.txt", "w", encoding="utf-8") as f:
    def check(name, url, headers=None, params=None):
        msg = f"--- {name} ---\nURL: {url}\n"
        if headers: msg += f"Headers: {headers.keys()}\n"
        if params: msg += f"Params: {params}\n"
        try:
            resp = requests.get(url, headers=headers, params=params, verify=False, timeout=5)
            msg += f"Status: {resp.status_code}\nResponse: {resp.text[:100]}\n\n"
        except Exception as e:
            msg += f"Error: {e}\n\n"
        print(msg)
        f.write(msg)

    # 1. SustainableDB Auth Probing
    # Try 1: Header 'ApiKey'
    check("Sust: Header 'ApiKey'", f"{base_sust}/search", params={"q": "apple"}, headers={"ApiKey": api_key})
    # Try 2: Query Param 'ApiKey'
    check("Sust: Query 'ApiKey'", f"{base_sust}/search", params={"q": "apple", "ApiKey": api_key})
    # Try 3: Auth Header 'ApiKey <token>'
    check("Sust: Auth 'ApiKey'", f"{base_sust}/search", params={"q": "apple"}, headers={"Authorization": f"ApiKey {api_key}"})
    
    # 2. DietRx Auth Probing
    check("DietRx: Header 'ApiKey'", f"{base_diet}/all-details", headers={"ApiKey": api_key})
    check("DietRx: Query 'ApiKey'", f"{base_diet}/all-details", params={"ApiKey": api_key})
