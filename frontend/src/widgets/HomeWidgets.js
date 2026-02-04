"""
Home Screen Widgets(iOS / Android)
Real - time widgets that update without opening the app
"""

// Widget configurations for iOS (WidgetKit) and Android (Glance)

// SMALL WIDGET - Streak Counter
export const SmallStreakWidget = `
{
  "type": "small",
  "title": "Streak",
  "content": {
    "icon": "🔥",
    "value": "{streak_days}",
    "label": "days",
    "background": "linear-gradient(135deg, #EF4444, #DC2626)",
    "updateInterval": "hourly"
  }
}
`;

// MEDIUM WIDGET - Daily Progress
export const MediumProgressWidget = `
{
  "type": "medium",
  "title": "Today's Progress",
  "content": {
    "rings": [
      {
        "label": "Health",
        "percentage": "{health_percentage}",
        "color": "#10B981"
      },
      {
        "label": "Taste",
        "percentage": "{taste_percentage}",
        "color": "#8B5CF6"
      },
      {
        "label": "Variety",
        "percentage": "{variety_percentage}",
        "color": "#F59E0B"
      }
    ],
    "nextMeal": {
      "type": "{next_meal_type}",
      "time": "{next_meal_time}",
      "icon": "🍽️"
    },
    "updateInterval": "15min"
  }
}
`;

// LARGE WIDGET - Recommended Meal
export const LargeRecommendationWidget = `
{
  "type": "large",
  "title": "Recommended for {meal_type}",
  "content": {
    "recipe": {
      "name": "{recipe_name}",
      "image": "{recipe_image_url}",
      "emoji": "{recipe_emoji}",
      "healthScore": "{health_score}",
      "tasteScore": "{taste_score}",
      "calories": "{calories}",
      "cookTime": "{cook_time}"
    },
    "action": {
      "label": "Tap to start cooking",
      "deeplink": "nutriflavorOS://recipe/{recipe_id}"
    },
    "sustainability": {
      "carbonSaved": "{carbon_saved}",
      "icon": "🌍"
    },
    "updateInterval": "30min"
  }
}
`;

// Widget Update Service (Backend)
export const widgetUpdateService = `
"""
Widget Update Service
Pushes real-time updates to home screen widgets
"""
from typing import Dict
import json
from datetime import datetime

class WidgetUpdateService:
    def __init__(self):
        self.widget_data = {}
    
    def update_streak_widget(self, user_id: str, streak_days: int):
        """Update small streak widget"""
        self.widget_data[f"{user_id}_small"] = {
            "streak_days": streak_days,
            "last_updated": datetime.now().isoformat()
        }
        
        # Push to iOS/Android widget service
        self._push_widget_update(user_id, "small", {
            "icon": "🔥",
            "value": str(streak_days),
            "label": "days"
        })
    
    def update_progress_widget(self, user_id: str, health: float, taste: float, variety: float, next_meal: Dict):
        """Update medium progress widget"""
        self.widget_data[f"{user_id}_medium"] = {
            "health_percentage": int(health * 100),
            "taste_percentage": int(taste * 100),
            "variety_percentage": int(variety * 100),
            "next_meal_type": next_meal.get("type", "Dinner"),
            "next_meal_time": next_meal.get("time", "6:00 PM"),
            "last_updated": datetime.now().isoformat()
        }
        
        self._push_widget_update(user_id, "medium", self.widget_data[f"{user_id}_medium"])
    
    def update_recommendation_widget(self, user_id: str, recipe: Dict):
        """Update large recommendation widget"""
        self.widget_data[f"{user_id}_large"] = {
            "recipe_name": recipe["name"],
            "recipe_emoji": recipe.get("emoji", "🍽️"),
            "health_score": int(recipe["health_score"] * 100),
            "taste_score": int(recipe["taste_score"] * 100),
            "calories": recipe["calories"],
            "cook_time": recipe.get("cook_time", "30 min"),
            "carbon_saved": recipe.get("carbon_saved", 0),
            "recipe_id": recipe["id"],
            "last_updated": datetime.now().isoformat()
        }
        
        self._push_widget_update(user_id, "large", self.widget_data[f"{user_id}_large"])
    
    def _push_widget_update(self, user_id: str, widget_type: str, data: Dict):
        """Push update to iOS/Android widget service"""
        # iOS: Use APNs (Apple Push Notification service)
        # Android: Use Firebase Cloud Messaging
        
        payload = {
            "user_id": user_id,
            "widget_type": widget_type,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        # Send to push notification service
        print(f"Widget update pushed: {widget_type} for user {user_id}")
        return payload

# Global instance
widget_service = WidgetUpdateService()
`;

export default {
    SmallStreakWidget,
    MediumProgressWidget,
    LargeRecommendationWidget,
    widgetUpdateService
};
