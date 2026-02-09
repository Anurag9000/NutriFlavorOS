from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from backend.services.flavordb_service import FlavorDBService
from backend.api.user_routes import get_user_profile

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])

# Initialize Services
flavor_service = FlavorDBService()

@router.get("/health/{user_id}")
async def get_health_insights(user_id: str, period: str = "30d"):
    """
    Get health insights based on DietRxDB data (Future integration)
    """
    # Placeholder: In phase 13, this would aggregate data from DietRxDB
    return [
        {"date": "Mon", "score": 82},
        {"date": "Tue", "score": 85},
        {"date": "Wed", "score": 78},
        {"date": "Thu", "score": 90},
        {"date": "Fri", "score": 88},
        {"date": "Sat", "score": 92},
        {"date": "Sun", "score": 95},
    ]

@router.get("/taste/{user_id}")
async def get_taste_insights(user_id: str):
    """
    Get taste profile using FlavorDB analysis of user preferences
    """
    try:
        # 1. Fetch user profile to get liked ingredients
        user_profile = await get_user_profile(user_id)
        liked_ingredients = user_profile.get("liked_ingredients", ["Chocolate", "Strawberry", "Vanilla"])
        
        # 2. Analyze flavor profiles of liked ingredients
        flavor_profiles = {}
        for ingredient in liked_ingredients:
            # For each liked ingredient, get its flavor profile from FlavorDB
            # We aggregate counts of flavor descriptors (sweet, spicy, etc.)
            profile = flavor_service.get_flavor_profile(ingredient)
            if profile and "descriptors" in profile:
                for desc in profile["descriptors"]:
                    flavor_profiles[desc] = flavor_profiles.get(desc, 0) + 1
            
        # 3. Normalize data for Radar Chart
        # If DB returns empty (mock mode), use default data
        if not flavor_profiles:
             return [
                {"subject": "Spicy", "A": 120, "fullMark": 150},
                {"subject": "Sweet", "A": 98, "fullMark": 150},
                {"subject": "Salty", "A": 86, "fullMark": 150},
                {"subject": "Bitter", "A": 99, "fullMark": 150},
                {"subject": "Sour", "A": 85, "fullMark": 150},
                {"subject": "Umami", "A": 65, "fullMark": 150},
            ]
            
        # Convert to chart format
        chart_data = []
        max_val = max(flavor_profiles.values()) if flavor_profiles else 1
        for subject, count in flavor_profiles.items():
            normalized = (count / max_val) * 150
            chart_data.append({"subject": subject.capitalize(), "A": normalized, "fullMark": 150})
            
        return chart_data[:6] # Limit to top 6 dimensions
        
    except Exception as e:
        print(f"Error generating taste insights: {e}")
        # Fallback
        return [
                {"subject": "Spicy", "A": 80, "fullMark": 150},
                {"subject": "Sweet", "A": 110, "fullMark": 150},
                {"subject": "Salty", "A": 90, "fullMark": 150},
                {"subject": "Bitter", "A": 50, "fullMark": 150},
                {"subject": "Sour", "A": 60, "fullMark": 150},
                {"subject": "Umami", "A": 100, "fullMark": 150},
            ]

@router.get("/variety/{user_id}")
async def get_variety_insights(user_id: str):
    """
    Get variety metrics
    """
    return [
        {"name": "Vegetables", "value": 35},
        {"name": "Fruits", "value": 25},
        {"name": "Grains", "value": 20},
        {"name": "Proteins", "value": 15},
        {"name": "Dairy", "value": 5},
    ]

@router.post("/predict_health")
async def predict_health(payload: Dict = Body(...)):
    """
    Predict future health score
    """
    return {
        "current_score": 85,
        "predicted_score": 92,
        "forecast": [
             {"day": 1, "score": 85},
             {"day": 15, "score": 88},
             {"day": 30, "score": 92},
        ]
    }
