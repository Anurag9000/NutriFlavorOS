
import requests
import sys

endpoints = [
    "http://cosylab.iiitd.edu.in:6969/recipe2-api/recipe/recipeofday",
    "https://cosylab.iiitd.edu.in/recipe2-api/recipe/recipeofday",
    "http://cosylab.iiitd.edu/recipe2-api/recipe/recipeofday",
    "http://cosylab.iiitd.edu.in/recipe2-api/recipe/recipeofday" # Standard http
]

headers = {
    "Authorization": "Bearer TEST_KEY", # Using dummy key to test connectivity
    "Content-Type": "application/json"
}

print("Testing API Connectivity (Concise Mode)...")
for url in endpoints:
    try:
        response = requests.get(url, headers=headers, timeout=5)
        if response.status_code == 200:
            print(f"\n[SUCCESS] URL: {url}")
            print(f"Status Code: {response.status_code}")
            print(f"Content Preview: {response.text[:100]}")
        else:
            print(f"[FAILED] URL: {url} | Status: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] URL: {url} | Error: {str(e)[:50]}")
print("Done.")
