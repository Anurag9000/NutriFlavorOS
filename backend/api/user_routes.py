from fastapi import APIRouter, HTTPException, Body
from backend.models import UserProfile
from backend.services.dietrxdb_service import DietRxDBService
from typing import List, Dict
import json
import os

router = APIRouter(prefix="/api/v1/user", tags=["user"])

# Initialize Service
dietrx_service = DietRxDBService()

# Persistence File
USER_DB_FILE = "user_db.json"

def load_users():
    if os.path.exists(USER_DB_FILE):
        try:
            with open(USER_DB_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_users(users):
    with open(USER_DB_FILE, 'w') as f:
        json.dump(users, f, indent=2)

# Load users on startup
users_db = load_users()

@router.get("/{user_id}", response_model=UserProfile)
async def get_user_profile(user_id: str):
    """
    Get a user's profile with persistence
    """
    if user_id not in users_db:
        # Create default profile if new user
        default_profile = {
            "name": "New User",
            "age": 30,
            "weight_kg": 70.0,
            "height_cm": 170.0,
            "gender": "male",
            "activity_level": 1.4,
            "goal": "maintenance",
            "dietary_restrictions": [],
            "health_conditions": [],
            "medications": []
        }
        users_db[user_id] = default_profile
        save_users(users_db)
        
    return users_db[user_id]

@router.put("/{user_id}", response_model=UserProfile)
async def update_user_profile(user_id: str, profile: UserProfile):
    """
    Update a user's profile
    """
    users_db[user_id] = profile.dict()
    save_users(users_db)
    return profile

@router.post("/{user_id}/health_condition")
async def add_health_condition(user_id: str, payload: Dict = Body(...)):
    """
    Add a health condition and validate with DietRxDB
    """
    condition = payload.get("condition")
    if not condition:
        raise HTTPException(status_code=400, detail="Condition required")
        
    # Validation with DietRxDB
    # We check if the disease exists in the database
    # This ensures we have data for it later
    try:
        disease_info = dietrx_service.get_disease_info(condition)
        is_known = "name" in disease_info or len(disease_info) > 0
    except:
        is_known = False
        
    # Update profile
    user_profile = users_db.get(user_id, {})
    current_conditions = user_profile.get("health_conditions", [])
    
    if condition not in current_conditions:
        current_conditions.append(condition)
        user_profile["health_conditions"] = current_conditions
        users_db[user_id] = user_profile
        save_users(users_db)
        
    return {
        "status": "success", 
        "message": f"Added condition: {condition}",
        "dataset_verified": is_known
    }

@router.post("/{user_id}/medication")
async def add_medication(user_id: str, payload: Dict = Body(...)):
    """
    Add a medication
    """
    medication = payload.get("medication")
    if not medication:
        raise HTTPException(status_code=400, detail="Medication required")
        
    # Update profile
    user_profile = users_db.get(user_id, {})
    current_meds = user_profile.get("medications", [])
    
    if medication not in current_meds:
        current_meds.append(medication)
        user_profile["medications"] = current_meds
        users_db[user_id] = user_profile
        save_users(users_db)
        
    return {"status": "success", "message": f"Added medication: {medication}"}
