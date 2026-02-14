
import os
import json
import sys

# Simulate being in backend/api/analytics_routes.py
# current file is scripts/debug_demo_load.py
# we need to construct path relative to backend/api/
# But wait, the code uses __file__.
# Let's verify what the path resolves to if we pretend we are in backend/api/

def test_load():
    # Construct the path exactly as in the route file
    # We need to simulate the location of analytics_routes.py
    # d:\Finished Projects\Resume\FoodScope\backend\api\analytics_routes.py
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # d:\Finished Projects\Resume\FoodScope
    route_file_sim = os.path.join(base_dir, "backend", "api", "analytics_routes.py")
    
    print(f"Simulated route file: {route_file_sim}")
    
    # Logic from route:
    # path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "demo_data.json")
    # dirname(route_file) -> backend/api
    # dirname(backend/api) -> backend
    # join(backend, "data", "demo_data.json")
    
    backend_dir = os.path.dirname(os.path.dirname(route_file_sim))
    data_path = os.path.join(backend_dir, "data", "demo_data.json")
    
    print(f"Calculated data path: {data_path}")
    
    if os.path.exists(data_path):
        print("File FOUND!")
        try:
            with open(data_path, 'r') as f:
                data = json.load(f)
            print(f"Keys: {list(data.keys())}")
            print(f"Analytics keys: {list(data.get('analytics', {}).keys())}")
            print(f"Health History length: {len(data.get('analytics', {}).get('health_history', []))}")
        except Exception as e:
            print(f"JSON Parse Error: {e}")
    else:
        print("File NOT FOUND!")

if __name__ == "__main__":
    test_load()
