from datetime import datetime, timedelta
import json
import os
from typing import Dict, Optional
from backend.models import PlanResponse

# Persistence File
MEAL_PLAN_DB_FILE = "meal_plans.json"

def load_meal_plans() -> Dict[str, Dict]:
    """Load meal plans from JSON file"""
    if os.path.exists(MEAL_PLAN_DB_FILE):
        try:
            with open(MEAL_PLAN_DB_FILE, 'r') as f:
                data = json.load(f)
                # Convert strings back to objects
                restored_cache = {}
                for uid, entry in data.items():
                    restored_cache[uid] = {
                        "plan": PlanResponse(**entry["plan"]),
                        "created_at": datetime.fromisoformat(entry["created_at"]),
                        "expires_at": datetime.fromisoformat(entry["expires_at"])
                    }
                return restored_cache
        except Exception as e:
            print(f"Error loading meal plans: {e}")
            return {}
    return {}

# In-memory cache for meal plans (user_id -> plan)
# Loaded from file at startup
meal_plan_cache: Dict[str, Dict] = load_meal_plans()

def save_meal_plans():
    """Save meal plans to JSON file"""
    try:
        data_to_save = {}
        for uid, entry in meal_plan_cache.items():
            data_to_save[uid] = {
                "plan": entry["plan"].dict(),
                "created_at": entry["created_at"].isoformat(),
                "expires_at": entry["expires_at"].isoformat()
            }
        
        with open(MEAL_PLAN_DB_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=2)
    except Exception as e:
        print(f"Error saving meal plans: {e}")

def cache_plan(user_id: str, plan: PlanResponse):
    """Store plan in cache with timestamp"""
    meal_plan_cache[user_id] = {
        "plan": plan,
        "created_at": datetime.now(),
        "expires_at": datetime.now() + timedelta(days=7)  # Plans valid for 7 days
    }
    save_meal_plans()

def get_cached_plan(user_id: str) -> Optional[PlanResponse]:
    """Retrieve plan from cache if it exists and hasn't expired"""
    if user_id not in meal_plan_cache:
        return None
    
    cached = meal_plan_cache[user_id]
    if datetime.now() > cached["expires_at"]:
        # Plan expired, remove from cache
        del meal_plan_cache[user_id]
        save_meal_plans()
        return None
    
    return cached["plan"]

def update_cached_day(user_id: str, day_index: int, new_day):
    """Update a specific day in the cached plan"""
    if user_id in meal_plan_cache:
        cached_plan = meal_plan_cache[user_id]["plan"]
        if 0 <= day_index < len(cached_plan.days):
            cached_plan.days[day_index] = new_day
            save_meal_plans()
            return True
    return False
