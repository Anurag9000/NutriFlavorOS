
import sys
import os
import json

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import APIConfig
from dotenv import load_dotenv

def check_env():
    print("--- Environment Variable Check ---")
    
    # Check raw os.environ
    print(f"RECIPEDB_BASE_URL (os.environ): {os.environ.get('RECIPEDB_BASE_URL')}")
    print(f"FLAVORDB_BASE_URL (os.environ): {os.environ.get('FLAVORDB_BASE_URL')}")
    
    # Check what dotenv finds
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", ".env")
    print(f"Checking for .env at: {env_path}")
    if os.path.exists(env_path):
        print(".env file FOUND")
        with open(env_path, 'r') as f:
            print(f"Content:\n{f.read()}")
    else:
        print(".env file NOT FOUND")

    print("\n--- APIConfig Values ---")
    print(f"APIConfig.RECIPEDB_BASE_URL: {APIConfig.RECIPEDB_BASE_URL}")
    print(f"APIConfig.FLAVORDB_BASE_URL: {APIConfig.FLAVORDB_BASE_URL}")
    print(f"APIConfig.SUSTAINABLEFOODDB_BASE_URL: {APIConfig.SUSTAINABLEFOODDB_BASE_URL}")

if __name__ == "__main__":
    check_env()
