import requests

def test():
    print("Testing Root...")
    try:
        r = requests.get("http://127.0.0.1:8000/", timeout=5)
        print(f"Root Status: {r.status_code}")
        print(f"Root Text: {r.text}")
    except Exception as e:
        print(f"Root Error: {e}")

    print("\nTesting Auth...")
    try:
        r = requests.post("http://127.0.0.1:8000/api/v1/auth/login", 
                          json={"email": "a", "password": "b"}, timeout=5)
        print(f"Auth Status: {r.status_code}")
        print(f"Auth Text: {r.text}")
    except Exception as e:
        print(f"Auth Error: {e}")

if __name__ == "__main__":
    test()
