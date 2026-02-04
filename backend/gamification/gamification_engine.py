"""
Gamification & Social Features with Leaderboards
Makes sustainability tracking engaging and competitive
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import json
from pathlib import Path

class GamificationEngine:
    """
    Gamification system for nutrition and sustainability
    """
    
    def __init__(self):
        self.achievements_db = Path("backend/data/achievements.json")
        self.leaderboard_db = Path("backend/data/leaderboards.json")
        self.user_stats_db = Path("backend/data/user_stats.json")
        
        # Ensure directories exist
        self.achievements_db.parent.mkdir(parents=True, exist_ok=True)
        
        # Achievement definitions
        self.achievements = {
            # Sustainability Achievements
            "eco_warrior": {
                "name": "Eco Warrior",
                "description": "Save 100kg CO2 in a month",
                "threshold": 100,
                "metric": "carbon_saved",
                "badge": "🌍",
                "points": 500
            },
            "tree_planter": {
                "name": "Tree Planter",
                "description": "Save equivalent of 10 trees",
                "threshold": 10,
                "metric": "trees_equivalent",
                "badge": "🌳",
                "points": 300
            },
            "water_saver": {
                "name": "Water Saver",
                "description": "Save 1000L of water",
                "threshold": 1000,
                "metric": "water_saved",
                "badge": "💧",
                "points": 400
            },
            
            # Variety Achievements
            "flavor_explorer": {
                "name": "Flavor Explorer",
                "description": "Try 50 unique ingredients",
                "threshold": 50,
                "metric": "unique_ingredients",
                "badge": "🗺️",
                "points": 300
            },
            "cuisine_master": {
                "name": "Cuisine Master",
                "description": "Try 10 different cuisines",
                "threshold": 10,
                "metric": "unique_cuisines",
                "badge": "👨‍🍳",
                "points": 400
            },
            
            # Health Achievements
            "macro_master": {
                "name": "Macro Master",
                "description": "Hit macro targets 30 days straight",
                "threshold": 30,
                "metric": "macro_streak",
                "badge": "🎯",
                "points": 600
            },
            "health_champion": {
                "name": "Health Champion",
                "description": "Maintain 90%+ health score for a month",
                "threshold": 30,
                "metric": "health_streak",
                "badge": "💪",
                "points": 500
            },
            
            # Taste Achievements
            "taste_adventurer": {
                "name": "Taste Adventurer",
                "description": "Rate 100 meals",
                "threshold": 100,
                "metric": "meals_rated",
                "badge": "⭐",
                "points": 200
            },
            
            # Social Achievements
            "team_player": {
                "name": "Team Player",
                "description": "Complete 5 team challenges",
                "threshold": 5,
                "metric": "team_challenges",
                "badge": "🤝",
                "points": 400
            }
        }
        
    def update_user_stats(self, user_id: str, stats: Dict):
        """
        Update user statistics and check for achievements
        
        Args:
            user_id: User identifier
            stats: Dictionary of metrics to update
        """
        # Load current stats
        user_stats = self._load_user_stats(user_id)
        
        # Update stats
        for metric, value in stats.items():
            if metric in user_stats:
                user_stats[metric] += value
            else:
                user_stats[metric] = value
        
        # Check for new achievements
        new_achievements = self._check_achievements(user_id, user_stats)
        
        # Save updated stats
        self._save_user_stats(user_id, user_stats)
        
        return {
            "updated_stats": user_stats,
            "new_achievements": new_achievements,
            "total_points": user_stats.get("total_points", 0)
        }
    
    def log_meal_impact(self, user_id: str, meal_data: Dict) -> Dict:
        """
        Log environmental and health impact of a meal
        
        Args:
            user_id: User identifier
            meal_data: {
                "carbon_footprint": float (kg CO2),
                "health_score": float (0-1),
                "variety_score": float (0-1),
                "taste_rating": float (0-1)
            }
        
        Returns:
            Impact summary with visual comparisons
        """
        carbon = meal_data.get("carbon_footprint", 0)
        
        # Calculate savings compared to average meal (2.5 kg CO2)
        average_meal_carbon = 2.5
        carbon_saved = max(0, average_meal_carbon - carbon)
        
        # Visual impact calculations
        trees_equivalent = carbon_saved / 21  # 1 tree absorbs ~21kg CO2/year
        car_miles_equivalent = carbon_saved / 0.404  # 1 mile = 0.404 kg CO2
        water_saved = carbon_saved * 50  # Rough estimate: 50L water per kg CO2
        
        # Update user stats
        stats_update = {
            "carbon_saved": carbon_saved,
            "trees_equivalent": trees_equivalent,
            "water_saved": water_saved,
            "meals_logged": 1,
            "total_points": self._calculate_meal_points(meal_data)
        }
        
        if meal_data.get("taste_rating"):
            stats_update["meals_rated"] = 1
        
        result = self.update_user_stats(user_id, stats_update)
        
        # Add visual impact
        result["visual_impact"] = {
            "carbon_saved_kg": round(carbon_saved, 2),
            "trees_equivalent": round(trees_equivalent, 3),
            "car_miles_saved": round(car_miles_equivalent, 1),
            "water_saved_liters": round(water_saved, 1),
            "comparison": self._get_impact_comparison(carbon_saved)
        }
        
        return result
    
    def get_leaderboard(self, leaderboard_type: str = "carbon_saved", 
                       period: str = "month", limit: int = 100) -> List[Dict]:
        """
        Get leaderboard rankings
        
        Args:
            leaderboard_type: "carbon_saved", "total_points", "health_streak", etc.
            period: "week", "month", "all_time"
            limit: Number of top users to return
        
        Returns:
            List of {rank, user_id, username, score, badge}
        """
        # Load all user stats
        all_stats = self._load_all_user_stats()
        
        # Filter by period if needed
        if period != "all_time":
            all_stats = self._filter_by_period(all_stats, period)
        
        # Sort by metric
        leaderboard = []
        for user_id, stats in all_stats.items():
            score = stats.get(leaderboard_type, 0)
            leaderboard.append({
                "user_id": user_id,
                "username": stats.get("username", f"User{user_id[:8]}"),
                "score": score,
                "badge": self._get_user_badge(stats)
            })
        
        leaderboard.sort(key=lambda x: x["score"], reverse=True)
        
        # Add ranks
        for i, entry in enumerate(leaderboard[:limit]):
            entry["rank"] = i + 1
        
        return leaderboard[:limit]
    
    def get_user_rank(self, user_id: str, leaderboard_type: str = "carbon_saved") -> Dict:
        """Get user's current rank on leaderboard"""
        leaderboard = self.get_leaderboard(leaderboard_type, limit=10000)
        
        for entry in leaderboard:
            if entry["user_id"] == user_id:
                return {
                    "rank": entry["rank"],
                    "score": entry["score"],
                    "percentile": round((1 - entry["rank"] / len(leaderboard)) * 100, 1)
                }
        
        return {"rank": None, "score": 0, "percentile": 0}
    
    def create_challenge(self, challenge_data: Dict) -> str:
        """
        Create a team or individual challenge
        
        Args:
            challenge_data: {
                "name": str,
                "type": "team" or "individual",
                "goal": str (e.g., "carbon_saved"),
                "target": float,
                "duration_days": int,
                "participants": List[str]
            }
        
        Returns:
            challenge_id
        """
        challenge_id = f"challenge_{datetime.now().timestamp()}"
        
        challenge = {
            "id": challenge_id,
            "name": challenge_data["name"],
            "type": challenge_data["type"],
            "goal": challenge_data["goal"],
            "target": challenge_data["target"],
            "start_date": datetime.now().isoformat(),
            "end_date": (datetime.now() + timedelta(days=challenge_data["duration_days"])).isoformat(),
            "participants": challenge_data["participants"],
            "progress": {user: 0 for user in challenge_data["participants"]},
            "status": "active"
        }
        
        self._save_challenge(challenge)
        return challenge_id
    
    def get_user_achievements(self, user_id: str) -> List[Dict]:
        """Get all achievements earned by user"""
        user_stats = self._load_user_stats(user_id)
        earned = user_stats.get("achievements", [])
        
        achievements_list = []
        for achievement_id in earned:
            if achievement_id in self.achievements:
                achievement = self.achievements[achievement_id].copy()
                achievement["id"] = achievement_id
                achievement["earned_date"] = user_stats.get(f"achievement_{achievement_id}_date")
                achievements_list.append(achievement)
        
        return achievements_list
    
    def get_monthly_impact_summary(self, user_id: str) -> Dict:
        """
        Get user's monthly impact summary with visual comparisons
        """
        user_stats = self._load_user_stats(user_id)
        
        carbon_saved = user_stats.get("carbon_saved", 0)
        trees = carbon_saved / 21
        water_saved = user_stats.get("water_saved", 0)
        
        return {
            "carbon_saved_kg": round(carbon_saved, 2),
            "trees_equivalent": round(trees, 2),
            "water_saved_liters": round(water_saved, 1),
            "meals_logged": user_stats.get("meals_logged", 0),
            "achievements_earned": len(user_stats.get("achievements", [])),
            "total_points": user_stats.get("total_points", 0),
            "visual_comparisons": [
                f"🌳 Equivalent to planting {int(trees)} trees",
                f"🚗 Saved {int(carbon_saved / 0.404)} miles of driving",
                f"💧 Saved {int(water_saved)} liters of water",
                f"🏠 Powered a home for {int(carbon_saved / 30)} days"
            ]
        }
    
    def _check_achievements(self, user_id: str, user_stats: Dict) -> List[Dict]:
        """Check if user earned any new achievements"""
        earned_achievements = user_stats.get("achievements", [])
        new_achievements = []
        
        for achievement_id, achievement in self.achievements.items():
            if achievement_id in earned_achievements:
                continue  # Already earned
            
            metric = achievement["metric"]
            threshold = achievement["threshold"]
            current_value = user_stats.get(metric, 0)
            
            if current_value >= threshold:
                # Achievement unlocked!
                earned_achievements.append(achievement_id)
                user_stats["achievements"] = earned_achievements
                user_stats[f"achievement_{achievement_id}_date"] = datetime.now().isoformat()
                user_stats["total_points"] = user_stats.get("total_points", 0) + achievement["points"]
                
                new_achievements.append({
                    "id": achievement_id,
                    "name": achievement["name"],
                    "description": achievement["description"],
                    "badge": achievement["badge"],
                    "points": achievement["points"]
                })
        
        return new_achievements
    
    def _calculate_meal_points(self, meal_data: Dict) -> int:
        """Calculate points earned from a meal"""
        points = 0
        
        # Health points
        health_score = meal_data.get("health_score", 0)
        points += int(health_score * 10)
        
        # Sustainability points
        carbon = meal_data.get("carbon_footprint", 2.5)
        if carbon < 2.5:  # Better than average
            points += int((2.5 - carbon) * 5)
        
        # Variety points
        variety_score = meal_data.get("variety_score", 0)
        points += int(variety_score * 5)
        
        return points
    
    def _get_impact_comparison(self, carbon_saved: float) -> str:
        """Get human-readable impact comparison"""
        if carbon_saved < 0.5:
            return "Small impact - keep going!"
        elif carbon_saved < 1.0:
            return "Good choice! 🌱"
        elif carbon_saved < 2.0:
            return "Great impact! 🌟"
        else:
            return "Amazing! You're a sustainability champion! 🏆"
    
    def _get_user_badge(self, stats: Dict) -> str:
        """Get user's highest badge"""
        achievements = stats.get("achievements", [])
        if not achievements:
            return "🌱"  # Beginner
        
        # Return badge of most recent achievement
        latest = achievements[-1]
        return self.achievements.get(latest, {}).get("badge", "⭐")
    
    def _load_user_stats(self, user_id: str) -> Dict:
        """Load user statistics"""
        if not self.user_stats_db.exists():
            return {}
        
        with open(self.user_stats_db, "r") as f:
            all_stats = json.load(f)
        
        return all_stats.get(user_id, {})
    
    def _save_user_stats(self, user_id: str, stats: Dict):
        """Save user statistics"""
        if self.user_stats_db.exists():
            with open(self.user_stats_db, "r") as f:
                all_stats = json.load(f)
        else:
            all_stats = {}
        
        all_stats[user_id] = stats
        
        with open(self.user_stats_db, "w") as f:
            json.dump(all_stats, f, indent=2)
    
    def _load_all_user_stats(self) -> Dict:
        """Load all user statistics"""
        if not self.user_stats_db.exists():
            return {}
        
        with open(self.user_stats_db, "r") as f:
            return json.load(f)
    
    def _filter_by_period(self, stats: Dict, period: str) -> Dict:
        """Filter stats by time period"""
        # TODO: Implement time-based filtering
        return stats
    
    def _save_challenge(self, challenge: Dict):
        """Save challenge data"""
        if self.leaderboard_db.exists():
            with open(self.leaderboard_db, "r") as f:
                challenges = json.load(f)
        else:
            challenges = {}
        
        challenges[challenge["id"]] = challenge
        
        with open(self.leaderboard_db, "w") as f:
            json.dump(challenges, f, indent=2)


# Global instance
gamification_engine = GamificationEngine()
