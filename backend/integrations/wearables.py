"""
Wearable Integration Service
Connects to external health APIs (Apple Health, Google Fit, Garmin)
Provides dynamic biometric-driven plan adjustments
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import random

class WearableSync:
    """
    Simulates and manages biometric data from wearable devices
    
    Data points:
    - Active Calories (Today)
    - Resting Heart Rate
    - Sleep Quality Score (0-100)
    - Stress Level
    - Blood Glucose (simulated CGM)
    """
    
    def __init__(self, user_id: str):
        self.user_id = user_id

    def get_real_time_biometrics(self) -> Dict[str, Any]:
        """
        In production, this calls external OAuth-protected APIs
        In prototype, it simulates dynamic health data
        """
        # Random variance for realistic simulation
        return {
            "active_calories": random.randint(300, 800),
            "resting_hr": random.randint(55, 75),
            "sleep_score": random.randint(65, 95),
            "stress_level": random.choice(["Low", "Moderate", "High"]),
            "timestamp": datetime.now().isoformat()
        }

    def calculate_caloric_adjustment(self, current_biometrics: Dict[str, Any]) -> int:
        """
        Calculate how many extra calories the user needs based on activity level
        """
        active_cals = current_biometrics.get("active_calories", 0)
        # We might suggest eating back 50-70% of active calories to stay in target
        return int(active_cals * 0.6)

    def get_micronutrient_recommendations(self, current_biometrics: Dict[str, Any]) -> List[str]:
        """
        Recommend specific nutrients based on biometric state
        """
        recs = []
        sleep = current_biometrics.get("sleep_score", 100)
        stress = current_biometrics.get("stress_level", "Low")
        
        if sleep < 70:
            recs.append("Magnesium-rich foods (Spinach, Almonds) to improve sleep quality")
        if stress == "High":
            recs.append("Omega-3 Fatty Acids (Salmon, Walnuts) to help manage cortisol")
            
        return recs

# Instance creation helper
def get_wearable_service(user_id: str) -> WearableSync:
    return WearableSync(user_id)
