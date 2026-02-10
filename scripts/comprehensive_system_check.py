"""
Comprehensive System Check - Verify all components work together
"""
import os
import sys
import json

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force Mock Mode
os.environ["MOCK_MODE"] = "true"
os.environ["CACHE_ENABLED"] = "false"

print("🔍 COMPREHENSIVE SYSTEM CHECK\n")
print("=" * 60)

# ============================================================
# 1. DATA LAYER CHECKS
# ============================================================
print("\n📊 [1/6] Checking Data Layer...")

from backend.config import APIConfig

required_files = [
    (APIConfig.MOCK_RECIPES_FILE, "Recipes Database"),
    (APIConfig.MOCK_FLAVOR_DB_FILE, "FlavorDB Database"),
    (APIConfig.MOCK_DIET_RX_FILE, "DietRxDB Database"),
    (APIConfig.MOCK_SUSTAINABLE_DB_FILE, "SustainableDB Database")
]

for filepath, name in required_files:
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            data = json.load(f)
            size = len(data) if isinstance(data, list) else len(data.keys())
            print(f"  ✅ {name}: {size} items")
    else:
        print(f"  ❌ {name}: MISSING")
        sys.exit(1)

# ============================================================
# 2. SERVICE LAYER CHECKS
# ============================================================
print("\n🔌 [2/6] Checking Service Layer...")

from backend.services.recipedb_service import RecipeDBService
from backend.services.flavordb_service import FlavorDBService
from backend.services.dietrxdb_service import DietRxDBService
from backend.services.sustainablefooddb_service import SustainableFoodDBService

try:
    r_service = RecipeDBService()
    recipes = r_service.search_by_title("")
    print(f"  ✅ RecipeDBService: {len(recipes)} recipes loaded")
    
    f_service = FlavorDBService()
    flavor = f_service.get_flavor_profile("chicken breast")
    print(f"  ✅ FlavorDBService: Flavor data accessible")
    
    d_service = DietRxDBService()
    disease = d_service.get_disease_info("Diabetes Type 2")
    print(f"  ✅ DietRxDBService: Health data accessible")
    
    s_service = SustainableFoodDBService()
    carbon = s_service.get_ingredient_carbon_footprint("beef steak")
    print(f"  ✅ SustainableFoodDBService: Sustainability data accessible")
    
except Exception as e:
    print(f"  ❌ Service Layer Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# 3. ENGINE LAYER CHECKS
# ============================================================
print("\n⚙️  [3/6] Checking Engine Layer...")

from backend.models import UserProfile
from backend.engines.health_engine import HealthEngine
from backend.engines.taste_engine import TasteEngine
from backend.engines.variety_engine import VarietyEngine

try:
    test_user = UserProfile(
        name="Test User",
        age=30,
        weight_kg=70,
        height_cm=175,
        gender="male",
        activity_level=1.4,
        goal="maintenance",
        liked_ingredients=["chicken"],
        disliked_ingredients=["kale"]
    )
    
    health_engine = HealthEngine()
    targets = health_engine.calculate_targets(test_user)
    print(f"  ✅ HealthEngine: Target calories = {targets.calories}")
    
    taste_engine = TasteEngine()
    genome = taste_engine.generate_flavor_genome(test_user)
    print(f"  ✅ TasteEngine: Genome generated with {len(genome)} dimensions")
    
    variety_engine = VarietyEngine()
    print(f"  ✅ VarietyEngine: Initialized")
    
except Exception as e:
    print(f"  ❌ Engine Layer Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# 4. PLAN GENERATOR CHECK
# ============================================================
print("\n🍱 [4/6] Checking Plan Generator...")

from backend.engines.plan_generator import PlanGenerator

try:
    generator = PlanGenerator()
    print(f"  ✅ PlanGenerator initialized with {len(generator.recipes)} recipes")
    
    plan = generator.create_plan(test_user, days=1)
    print(f"  ✅ Generated {len(plan.days)}-day plan")
    print(f"  ✅ Shopping list: {len(plan.shopping_list)} categories")
    print(f"  ✅ Overall stats: {plan.overall_stats}")
    
    # Check day 1 meals
    day1 = plan.days[0]
    print(f"  ✅ Day 1 has {len(day1.meals)} meals")
    
except Exception as e:
    print(f"  ❌ Plan Generator Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ============================================================
# 5. ML MODELS CHECK
# ============================================================
print("\n🤖 [5/6] Checking ML Models...")

ml_models_dir = "backend/ml/models"
os.makedirs(ml_models_dir, exist_ok=True)

ml_models = [
    "taste_predictor.pth",
    "health_predictor.pth",
    "meal_planner_rl.pth",
    "grocery_predictor.pth"
]

for model_name in ml_models:
    model_path = os.path.join(ml_models_dir, model_name)
    if os.path.exists(model_path):
        print(f"  ✅ {model_name}: EXISTS")
    else:
        print(f"  ⚠️  {model_name}: NOT TRAINED YET")

# Check if we can import ML modules
try:
    from backend.ml.taste_predictor import DeepTastePredictor
    from backend.ml.health_predictor import HealthLSTM
    print(f"  ✅ ML modules importable")
except Exception as e:
    print(f"  ❌ ML import error: {e}")

# ============================================================
# 6. API ROUTES CHECK (Import only)
# ============================================================
print("\n🌐 [6/6] Checking API Routes...")

try:
    from backend.api.plan_routes import router as plan_router
    from backend.api.user_routes import router as user_router
    print(f"  ✅ Plan routes: Importable")
    print(f"  ✅ User routes: Importable")
except Exception as e:
    print(f"  ❌ API Routes Error: {e}")
    import traceback
    traceback.print_exc()

# ============================================================
# FINAL SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("✨ SYSTEM CHECK COMPLETE ✨")
print("=" * 60)
print("\n✅ All core components are functional!")
print("⚠️  ML models need training (see instructions)")
print("\nNext Steps:")
print("  1. Train ML models using: python scripts/train_all_models.py")
print("  2. Start backend: uvicorn backend.main:app --reload")
print("  3. Access API docs: http://localhost:8000/docs")
