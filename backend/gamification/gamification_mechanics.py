"""
Gamification Mechanics - Daily Quests, Seasonal Events, Leveling
Retention-focused features that keep users coming back
"""
from typing import Dict, List
from datetime import datetime, timedelta
import random

class GamificationMechanics:
    """
    Daily quests, seasonal events, and leveling system
    """
    
    def __init__(self):
        self.daily_quests = self._generate_daily_quests()
        self.seasonal_events = self._get_seasonal_events()
        self.level_unlocks = self._define_level_unlocks()
    
    def _generate_daily_quests(self) -> List[Dict]:
        """Generate 3 random daily quests"""
        quest_pool = [
            {
                "id": "try_new_ingredient",
                "title": "Flavor Explorer",
                "description": "Try a new ingredient today",
                "points": 50,
                "icon": "🗺️",
                "progress": 0,
                "target": 1
            },
            {
                "id": "hit_macros",
                "title": "Macro Master",
                "description": "Hit all macro targets",
                "points": 100,
                "icon": "🎯",
                "progress": 0,
                "target": 1
            },
            {
                "id": "log_meals",
                "title": "Consistency King",
                "description": "Log 3 meals today",
                "points": 30,
                "icon": "📝",
                "progress": 0,
                "target": 3
            },
            {
                "id": "rate_meals",
                "title": "Taste Critic",
                "description": "Rate 2 meals",
                "points": 20,
                "icon": "⭐",
                "progress": 0,
                "target": 2
            },
            {
                "id": "eco_meal",
                "title": "Eco Warrior",
                "description": "Eat a low-carbon meal (<1kg CO2)",
                "points": 40,
                "icon": "🌍",
                "progress": 0,
                "target": 1
            },
            {
                "id": "variety_score",
                "title": "Diversity Champion",
                "description": "Achieve 80%+ variety score",
                "points": 60,
                "icon": "🌈",
                "progress": 0,
                "target": 1
            },
            {
                "id": "cook_new_recipe",
                "title": "Chef's Challenge",
                "description": "Cook a recipe you've never made",
                "points": 75,
                "icon": "👨‍🍳",
                "progress": 0,
                "target": 1
            }
        ]
        
        # Select 3 random quests
        return random.sample(quest_pool, 3)
    
    def _get_seasonal_events(self) -> Dict:
        """Get current seasonal event"""
        month = datetime.now().month
        
        events = {
            1: {
                "name": "New Year Detox",
                "description": "Start the year fresh with healthy eating",
                "icon": "🎊",
                "challenge": "Eat 90%+ health score for 7 days",
                "reward": "Detox Master Badge",
                "points": 500
            },
            6: {
                "name": "Summer Beach Body",
                "description": "Get fit for summer",
                "icon": "🏖️",
                "challenge": "High protein meals (30g+) for 14 days",
                "reward": "Beach Ready Badge",
                "points": 750
            },
            10: {
                "name": "Pumpkin Spice Everything",
                "description": "Celebrate fall flavors",
                "icon": "🎃",
                "challenge": "Try 10 seasonal ingredients",
                "reward": "Autumn Explorer Badge",
                "points": 600
            },
            12: {
                "name": "Holiday Comfort",
                "description": "Enjoy the season mindfully",
                "icon": "🎄",
                "challenge": "Balance indulgence with nutrition",
                "reward": "Mindful Eater Badge",
                "points": 650
            }
        }
        
        return events.get(month, {
            "name": "Monthly Challenge",
            "description": "Complete daily quests consistently",
            "icon": "🏆",
            "challenge": "30-day streak",
            "reward": "Consistency Champion Badge",
            "points": 1000
        })
    
    def _define_level_unlocks(self) -> Dict:
        """Define what features unlock at each level"""
        return {
            1: {
                "level": 1,
                "title": "Beginner",
                "icon": "🌱",
                "xp_required": 0,
                "unlocks": ["Basic meal planning", "Recipe browsing"]
            },
            5: {
                "level": 5,
                "title": "Novice",
                "icon": "🌿",
                "xp_required": 500,
                "unlocks": ["Recipe generator", "Flavor genome analysis"]
            },
            10: {
                "level": 10,
                "title": "Intermediate",
                "icon": "🌳",
                "xp_required": 1500,
                "unlocks": ["Meal planner RL", "Advanced analytics"]
            },
            20: {
                "level": 20,
                "title": "Advanced",
                "icon": "🏆",
                "xp_required": 4000,
                "unlocks": ["Grocery predictor", "Custom challenges"]
            },
            30: {
                "level": 30,
                "title": "Expert",
                "icon": "⭐",
                "xp_required": 8000,
                "unlocks": ["Beta features", "Priority support"]
            },
            50: {
                "level": 50,
                "title": "Master",
                "icon": "👑",
                "xp_required": 20000,
                "unlocks": ["All features", "Lifetime premium"]
            }
        }
    
    def update_quest_progress(self, user_id: str, quest_id: str, progress: int) -> Dict:
        """Update quest progress and check completion"""
        # Load user's daily quests
        quests = self.daily_quests  # In production, load from DB
        
        for quest in quests:
            if quest["id"] == quest_id:
                quest["progress"] = min(progress, quest["target"])
                
                if quest["progress"] >= quest["target"]:
                    # Quest completed!
                    return {
                        "completed": True,
                        "quest": quest,
                        "points_earned": quest["points"],
                        "message": f"🎉 Quest completed! +{quest['points']} points"
                    }
        
        return {"completed": False}
    
    def calculate_level(self, total_xp: int) -> Dict:
        """Calculate user level based on XP"""
        current_level = 1
        
        for level, data in sorted(self.level_unlocks.items()):
            if total_xp >= data["xp_required"]:
                current_level = level
            else:
                break
        
        # Calculate progress to next level
        current_level_data = self.level_unlocks[current_level]
        next_level = current_level + 1
        
        if next_level in self.level_unlocks:
            next_level_data = self.level_unlocks[next_level]
            xp_for_next = next_level_data["xp_required"] - current_level_data["xp_required"]
            xp_progress = total_xp - current_level_data["xp_required"]
            progress_percentage = (xp_progress / xp_for_next) * 100
        else:
            progress_percentage = 100  # Max level
            next_level_data = None
        
        return {
            "current_level": current_level,
            "title": current_level_data["title"],
            "icon": current_level_data["icon"],
            "total_xp": total_xp,
            "progress_to_next": round(progress_percentage, 1),
            "next_level": next_level_data,
            "unlocked_features": current_level_data["unlocks"]
        }
    
    def get_retention_notification(self, user_data: Dict) -> Dict:
        """Generate smart retention notification"""
        last_login = datetime.fromisoformat(user_data.get("last_login", datetime.now().isoformat()))
        hours_since_login = (datetime.now() - last_login).total_seconds() / 3600
        
        notifications = []
        
        # Meal reminder
        if hours_since_login >= 4:
            notifications.append({
                "type": "meal_reminder",
                "title": "Time for lunch!",
                "body": "Here's what we recommend...",
                "priority": "high"
            })
        
        # Streak warning
        if user_data.get("streak_days", 0) > 0 and hours_since_login >= 20:
            notifications.append({
                "type": "streak_warning",
                "title": f"Don't lose your {user_data['streak_days']}-day streak!",
                "body": "Log dinner to keep it going 🔥",
                "priority": "urgent"
            })
        
        # Achievement unlock
        if user_data.get("pending_achievements"):
            notifications.append({
                "type": "achievement",
                "title": "🎉 Achievement Unlocked!",
                "body": user_data["pending_achievements"][0],
                "priority": "medium"
            })
        
        # Social update
        if user_data.get("friend_activity"):
            notifications.append({
                "type": "social",
                "title": "Sarah just beat your high score!",
                "body": "Can you catch up?",
                "priority": "low"
            })
        
        return notifications[0] if notifications else None


# Global instance
gamification_mechanics = GamificationMechanics()
