"""
Social Gamification System for NutriFlavorOS
Includes achievements, leaderboards, challenges, and social features
"""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from enum import Enum
import json

class AchievementType(str, Enum):
    STREAK = "streak"
    VARIETY = "variety"
    HEALTH = "health"
    SOCIAL = "social"
    MILESTONE = "milestone"

class Achievement:
    """Individual achievement definition"""
    
    def __init__(self, id: str, name: str, description: str, 
                 achievement_type: AchievementType, points: int,
                 icon: str, requirement: Dict):
        self.id = id
        self.name = name
        self.description = description
        self.type = achievement_type
        self.points = points
        self.icon = icon
        self.requirement = requirement
        self.unlocked_by: List[str] = []  # User IDs

class Challenge:
    """Weekly/monthly challenge"""
    
    def __init__(self, id: str, name: str, description: str,
                 start_date: datetime, end_date: datetime,
                 goal: Dict, reward_points: int):
        self.id = id
        self.name = name
        self.description = description
        self.start_date = start_date
        self.end_date = end_date
        self.goal = goal
        self.reward_points = reward_points
        self.participants: Dict[str, float] = {}  # user_id -> progress

class SocialGamificationSystem:
    """
    Comprehensive gamification system with:
    - Achievements & badges
    - Streak tracking
    - Leaderboards
    - Weekly challenges
    - Social sharing
    - Points & levels
    """
    
    def __init__(self):
        self.achievements = self._initialize_achievements()
        self.challenges = []
        self.user_stats = {}  # user_id -> stats
        self.leaderboard = []
    
    def _initialize_achievements(self) -> List[Achievement]:
        """Initialize all available achievements"""
        return [
            # Streak Achievements
            Achievement(
                id="streak_7",
                name="Week Warrior",
                description="Log meals for 7 consecutive days",
                achievement_type=AchievementType.STREAK,
                points=100,
                icon="🔥",
                requirement={"streak_days": 7}
            ),
            Achievement(
                id="streak_30",
                name="Monthly Master",
                description="Log meals for 30 consecutive days",
                achievement_type=AchievementType.STREAK,
                points=500,
                icon="🏆",
                requirement={"streak_days": 30}
            ),
            Achievement(
                id="streak_100",
                name="Century Champion",
                description="Log meals for 100 consecutive days",
                achievement_type=AchievementType.STREAK,
                points=2000,
                icon="👑",
                requirement={"streak_days": 100}
            ),
            
            # Variety Achievements
            Achievement(
                id="variety_50",
                name="Flavor Explorer",
                description="Try 50 different recipes",
                achievement_type=AchievementType.VARIETY,
                points=200,
                icon="🌍",
                requirement={"unique_recipes": 50}
            ),
            Achievement(
                id="cuisine_10",
                name="Global Gourmet",
                description="Try recipes from 10 different cuisines",
                achievement_type=AchievementType.VARIETY,
                points=300,
                icon="🌏",
                requirement={"unique_cuisines": 10}
            ),
            
            # Health Achievements
            Achievement(
                id="weight_goal",
                name="Goal Getter",
                description="Reach your weight goal",
                achievement_type=AchievementType.HEALTH,
                points=1000,
                icon="🎯",
                requirement={"goal_reached": True}
            ),
            Achievement(
                id="macro_perfect",
                name="Macro Master",
                description="Hit macro targets 7 days in a row",
                achievement_type=AchievementType.HEALTH,
                points=300,
                icon="💪",
                requirement={"perfect_macro_days": 7}
            ),
            
            # Social Achievements
            Achievement(
                id="share_5",
                name="Social Butterfly",
                description="Share 5 meal plans with friends",
                achievement_type=AchievementType.SOCIAL,
                points=150,
                icon="🦋",
                requirement={"shares": 5}
            ),
            Achievement(
                id="review_10",
                name="Food Critic",
                description="Rate 10 recipes",
                achievement_type=AchievementType.SOCIAL,
                points=100,
                icon="⭐",
                requirement={"reviews": 10}
            ),
            
            # Milestone Achievements
            Achievement(
                id="first_plan",
                name="First Steps",
                description="Generate your first meal plan",
                achievement_type=AchievementType.MILESTONE,
                points=50,
                icon="🎉",
                requirement={"plans_generated": 1}
            ),
            Achievement(
                id="carbon_hero",
                name="Carbon Hero",
                description="Save 100kg CO2 through sustainable choices",
                achievement_type=AchievementType.MILESTONE,
                points=500,
                icon="🌱",
                requirement={"carbon_saved_kg": 100}
            )
        ]
    
    def track_user_activity(self, user_id: str, activity: Dict):
        """
        Track user activity and update stats
        
        Args:
            user_id: User identifier
            activity: {
                'type': 'meal_logged' | 'plan_generated' | 'recipe_rated' | 'shared',
                'data': {...}
            }
        """
        if user_id not in self.user_stats:
            self.user_stats[user_id] = self._initialize_user_stats()
        
        stats = self.user_stats[user_id]
        
        # Update stats based on activity type
        if activity['type'] == 'meal_logged':
            stats['meals_logged'] += 1
            stats['last_log_date'] = datetime.now()
            self._update_streak(user_id)
            
        elif activity['type'] == 'plan_generated':
            stats['plans_generated'] += 1
            
        elif activity['type'] == 'recipe_rated':
            stats['reviews'] += 1
            
        elif activity['type'] == 'shared':
            stats['shares'] += 1
            
        elif activity['type'] == 'recipe_tried':
            recipe_id = activity['data'].get('recipe_id')
            if recipe_id not in stats['unique_recipes']:
                stats['unique_recipes'].add(recipe_id)
            
            cuisine = activity['data'].get('cuisine')
            if cuisine and cuisine not in stats['unique_cuisines']:
                stats['unique_cuisines'].add(cuisine)
        
        # Check for new achievements
        new_achievements = self._check_achievements(user_id)
        
        # Update points and level
        self._update_level(user_id)
        
        return new_achievements
    
    def _initialize_user_stats(self) -> Dict:
        """Initialize stats for new user"""
        return {
            'points': 0,
            'level': 1,
            'streak_days': 0,
            'best_streak': 0,
            'meals_logged': 0,
            'plans_generated': 0,
            'reviews': 0,
            'shares': 0,
            'unique_recipes': set(),
            'unique_cuisines': set(),
            'achievements_unlocked': [],
            'last_log_date': None,
            'carbon_saved_kg': 0,
            'weight_progress': 0
        }
    
    def _update_streak(self, user_id: str):
        """Update user's streak"""
        stats = self.user_stats[user_id]
        last_log = stats['last_log_date']
        
        if last_log is None:
            stats['streak_days'] = 1
        else:
            days_diff = (datetime.now() - last_log).days
            
            if days_diff == 1:
                # Consecutive day
                stats['streak_days'] += 1
            elif days_diff == 0:
                # Same day, no change
                pass
            else:
                # Streak broken
                stats['best_streak'] = max(stats['best_streak'], stats['streak_days'])
                stats['streak_days'] = 1
    
    def _check_achievements(self, user_id: str) -> List[Achievement]:
        """Check if user unlocked new achievements"""
        stats = self.user_stats[user_id]
        new_achievements = []
        
        for achievement in self.achievements:
            # Skip if already unlocked
            if achievement.id in stats['achievements_unlocked']:
                continue
            
            # Check requirements
            unlocked = False
            
            if 'streak_days' in achievement.requirement:
                if stats['streak_days'] >= achievement.requirement['streak_days']:
                    unlocked = True
            
            if 'unique_recipes' in achievement.requirement:
                if len(stats['unique_recipes']) >= achievement.requirement['unique_recipes']:
                    unlocked = True
            
            if 'unique_cuisines' in achievement.requirement:
                if len(stats['unique_cuisines']) >= achievement.requirement['unique_cuisines']:
                    unlocked = True
            
            if 'plans_generated' in achievement.requirement:
                if stats['plans_generated'] >= achievement.requirement['plans_generated']:
                    unlocked = True
            
            if 'reviews' in achievement.requirement:
                if stats['reviews'] >= achievement.requirement['reviews']:
                    unlocked = True
            
            if 'shares' in achievement.requirement:
                if stats['shares'] >= achievement.requirement['shares']:
                    unlocked = True
            
            if unlocked:
                stats['achievements_unlocked'].append(achievement.id)
                stats['points'] += achievement.points
                achievement.unlocked_by.append(user_id)
                new_achievements.append(achievement)
        
        return new_achievements
    
    def _update_level(self, user_id: str):
        """Update user level based on points"""
        stats = self.user_stats[user_id]
        points = stats['points']
        
        # Level formula: level = floor(sqrt(points / 100))
        new_level = int((points / 100) ** 0.5) + 1
        stats['level'] = new_level
    
    def get_leaderboard(self, metric: str = 'points', limit: int = 100) -> List[Dict]:
        """
        Get leaderboard rankings
        
        Args:
            metric: 'points' | 'streak' | 'variety' | 'level'
            limit: Number of top users to return
        
        Returns:
            List of {user_id, rank, value, level}
        """
        leaderboard = []
        
        for user_id, stats in self.user_stats.items():
            if metric == 'points':
                value = stats['points']
            elif metric == 'streak':
                value = stats['streak_days']
            elif metric == 'variety':
                value = len(stats['unique_recipes'])
            elif metric == 'level':
                value = stats['level']
            else:
                value = stats['points']
            
            leaderboard.append({
                'user_id': user_id,
                'value': value,
                'level': stats['level'],
                'achievements': len(stats['achievements_unlocked'])
            })
        
        # Sort by value
        leaderboard.sort(key=lambda x: x['value'], reverse=True)
        
        # Add ranks
        for i, entry in enumerate(leaderboard[:limit]):
            entry['rank'] = i + 1
        
        return leaderboard[:limit]
    
    def create_challenge(self, name: str, description: str, 
                        duration_days: int, goal: Dict, reward_points: int) -> Challenge:
        """Create a new challenge"""
        start_date = datetime.now()
        end_date = start_date + timedelta(days=duration_days)
        
        challenge = Challenge(
            id=f"challenge_{len(self.challenges)}",
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            goal=goal,
            reward_points=reward_points
        )
        
        self.challenges.append(challenge)
        return challenge
    
    def get_user_dashboard(self, user_id: str) -> Dict:
        """Get comprehensive user dashboard"""
        if user_id not in self.user_stats:
            return {}
        
        stats = self.user_stats[user_id]
        
        # Calculate progress to next level
        current_level_points = (stats['level'] - 1) ** 2 * 100
        next_level_points = stats['level'] ** 2 * 100
        level_progress = (stats['points'] - current_level_points) / (next_level_points - current_level_points)
        
        return {
            'user_id': user_id,
            'level': stats['level'],
            'points': stats['points'],
            'level_progress': round(level_progress, 2),
            'streak_days': stats['streak_days'],
            'best_streak': stats['best_streak'],
            'achievements_unlocked': len(stats['achievements_unlocked']),
            'total_achievements': len(self.achievements),
            'unique_recipes_tried': len(stats['unique_recipes']),
            'cuisines_explored': len(stats['unique_cuisines']),
            'leaderboard_rank': self._get_user_rank(user_id),
            'recent_achievements': self._get_recent_achievements(user_id, limit=3)
        }
    
    def _get_user_rank(self, user_id: str) -> int:
        """Get user's rank on leaderboard"""
        leaderboard = self.get_leaderboard(metric='points')
        for entry in leaderboard:
            if entry['user_id'] == user_id:
                return entry['rank']
        return -1
    
    def _get_recent_achievements(self, user_id: str, limit: int = 3) -> List[Dict]:
        """Get user's recent achievements"""
        stats = self.user_stats[user_id]
        recent_ids = stats['achievements_unlocked'][-limit:]
        
        recent = []
        for achievement in self.achievements:
            if achievement.id in recent_ids:
                recent.append({
                    'id': achievement.id,
                    'name': achievement.name,
                    'icon': achievement.icon,
                    'points': achievement.points
                })
        
        return recent

# Singleton instance
_gamification_system = None

def get_gamification_system() -> SocialGamificationSystem:
    """Get or create gamification system instance"""
    global _gamification_system
    if _gamification_system is None:
        _gamification_system = SocialGamificationSystem()
    return _gamification_system
