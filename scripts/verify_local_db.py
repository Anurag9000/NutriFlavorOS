
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.services.flavordb_service import FlavorDBService
from backend.services.sustainablefooddb_service import SustainableFoodDBService

def verify_local_db():
    print("🧪 Verifying Local-First Architecture...")
    
    # 1. FlavorDB
    print("\n--- Testing FlavorDB Service ---")
    flavor_service = FlavorDBService()
    
    # Test "chicken breast" (known in local DB)
    profile = flavor_service.get_flavor_profile("chicken breast")
    if profile and "geraniol" in profile:
        print("✅ Found 'chicken breast' flavor profile (Local)")
    else:
        print("❌ Failed to find 'chicken breast' flavor")
        
    # Test "tomato" (known in local DB)
    groups = flavor_service.get_functional_groups("tomato")
    if "acid" in groups:
        print("✅ Found 'tomato' functional groups (Local)")
    else:
        print(f"❌ Failed to find 'tomato' groups. Got: {groups}")

    # 2. SustainableFoodDB
    print("\n--- Testing SustainableFoodDB Service ---")
    sust_service = SustainableFoodDBService()
    
    # Test "beef steak" (High impact)
    carbon = sust_service.get_ingredient_carbon_footprint("beef steak")
    if carbon > 20.0:
        print(f"✅ 'beef steak' carbon footprint: {carbon}kg (Correctly identified as high)")
    else:
        print(f"❌ 'beef steak' carbon footprint: {carbon}kg (Unexpected)")
        
    # Test "lentils" (Not in local DB? Checking file...)
    # Actually checking "tofu" which is in local DB
    carbon_tofu = sust_service.get_ingredient_carbon_footprint("tofu")
    if carbon_tofu > 0:
        print(f"✅ 'tofu' carbon footprint: {carbon_tofu}kg (Local)")
    else:
        print("❌ 'tofu' not found")

    print("\n✨ Verification Complete!")

if __name__ == "__main__":
    verify_local_db()
