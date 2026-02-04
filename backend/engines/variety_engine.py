"""
Variety Engine - Advanced diversity tracking and palate fatigue prevention
"""
from typing import List, Dict, Set
from collections import defaultdict, Counter
from backend.models import Recipe
from backend.services.recipedb_service import RecipeDBService

class VarietyEngine:
    """
    Advanced Variety Engine with:
    - Cuisine diversity tracking with enforcement
    - Texture balance analysis
    - Flavor family rotation
    - Configurable no-repeat windows
    - Ingredient frequency tracking over time
    - Advanced repetition checking
    """
    
    # Texture categories
    TEXTURES = {
        "crunchy": ["nuts", "crackers", "chips", "raw vegetables", "toast"],
        "creamy": ["yogurt", "cheese", "avocado", "hummus", "sauce"],
        "soft": ["banana", "tofu", "pasta", "rice", "bread"],
        "chewy": ["meat", "dried fruit", "caramel", "jerky"],
        "liquid": ["soup", "smoothie", "juice", "broth"]
    }
    
    # Flavor families (simplified)
    FLAVOR_FAMILIES = {
        "aromatic": ["garlic", "onion", "ginger", "herbs"],
        "citrus": ["lemon", "lime", "orange", "grapefruit"],
        "earthy": ["mushroom", "beet", "potato", "carrot"],
        "sweet": ["honey", "maple", "sugar", "fruit"],
        "savory": ["soy sauce", "miso", "cheese", "meat"]
    }
    
    def __init__(self, no_repeat_window: int = 7):
        """
        Args:
            no_repeat_window: Number of days before an ingredient can repeat (default 7)
        """
        self.recipe_service = RecipeDBService()
        self.no_repeat_window = no_repeat_window
        self.ingredient_history: List[Set[str]] = []  # Track ingredients per day
        self.cuisine_history: List[str] = []  # Track cuisines
        self.texture_history: List[Dict[str, int]] = []  # Track textures
        self.flavor_family_history: List[Set[str]] = []  # Track flavor families
    
    def update_history(self, recipes: List[Recipe], cuisine: str):
        """Update tracking history with new day's meals"""
        # Track ingredients
        day_ingredients = set()
        for recipe in recipes:
            day_ingredients.update(recipe.ingredients)
        self.ingredient_history.append(day_ingredients)
        
        # Track cuisine
        self.cuisine_history.append(cuisine)
        
        # Track textures
        day_textures = self._analyze_textures(recipes)
        self.texture_history.append(day_textures)
        
        # Track flavor families
        day_flavors = self._analyze_flavor_families(recipes)
        self.flavor_family_history.append(day_flavors)
        
        # Trim history to window size
        if len(self.ingredient_history) > self.no_repeat_window:
            self.ingredient_history.pop(0)
            self.cuisine_history.pop(0)
            self.texture_history.pop(0)
            self.flavor_family_history.pop(0)
    
    def score_variety(self, candidate: Recipe, recent_recipes: List[Recipe]) -> float:
        """
        Comprehensive variety score (0.0-1.0)
        Higher score = more variety
        """
        scores = []
        
        # 1. Ingredient uniqueness (30% weight)
        ingredient_score = self._score_ingredient_uniqueness(candidate, recent_recipes)
        scores.append(ingredient_score * 0.3)
        
        # 2. Cuisine diversity (25% weight)
        cuisine_score = self._score_cuisine_diversity(candidate)
        scores.append(cuisine_score * 0.25)
        
        # 3. Texture balance (20% weight)
        texture_score = self._score_texture_balance(candidate)
        scores.append(texture_score * 0.2)
        
        # 4. Flavor family rotation (15% weight)
        flavor_score = self._score_flavor_rotation(candidate)
        scores.append(flavor_score * 0.15)
        
        # 5. No-repeat window compliance (10% weight)
        repeat_score = self._score_no_repeat_compliance(candidate)
        scores.append(repeat_score * 0.1)
        
        return sum(scores)
    
    def _score_ingredient_uniqueness(self, candidate: Recipe, recent_recipes: List[Recipe]) -> float:
        """Score based on ingredient uniqueness"""
        if not recent_recipes:
            return 1.0
        
        # Get all recent ingredients
        recent_ingredients = set()
        for recipe in recent_recipes:
            recent_ingredients.update(recipe.ingredients)
        
        # Calculate overlap
        candidate_ingredients = set(candidate.ingredients)
        overlap = candidate_ingredients & recent_ingredients
        
        if not candidate_ingredients:
            return 0.5
        
        uniqueness = 1.0 - (len(overlap) / len(candidate_ingredients))
        return uniqueness
    
    def _score_cuisine_diversity(self, candidate: Recipe) -> float:
        """Score based on cuisine diversity"""
        if not self.cuisine_history:
            return 1.0
        
        # Get candidate cuisine (from recipe metadata or infer)
        candidate_cuisine = candidate.cuisine if hasattr(candidate, 'cuisine') else "unknown"
        
        # Count recent cuisine occurrences
        recent_cuisines = self.cuisine_history[-self.no_repeat_window:]
        cuisine_counts = Counter(recent_cuisines)
        
        # Penalize if cuisine was used recently
        if candidate_cuisine in cuisine_counts:
            # More recent = higher penalty
            penalty = cuisine_counts[candidate_cuisine] / len(recent_cuisines)
            return 1.0 - penalty
        
        return 1.0
    
    def _score_texture_balance(self, candidate: Recipe) -> float:
        """Score based on texture balance"""
        if not self.texture_history:
            return 1.0
        
        # Analyze candidate textures
        candidate_textures = self._get_recipe_textures(candidate)
        
        # Get recent texture distribution
        recent_texture_counts = Counter()
        for day_textures in self.texture_history[-3:]:  # Last 3 days
            recent_texture_counts.update(day_textures)
        
        # Score: prefer underrepresented textures
        score = 1.0
        for texture in candidate_textures:
            if texture in recent_texture_counts:
                # Penalize overused textures
                usage_ratio = recent_texture_counts[texture] / (len(self.texture_history[-3:]) * 3)
                score -= usage_ratio * 0.2
        
        return max(0.0, score)
    
    def _score_flavor_rotation(self, candidate: Recipe) -> float:
        """Score based on flavor family rotation"""
        if not self.flavor_family_history:
            return 1.0
        
        candidate_flavors = self._get_recipe_flavor_families(candidate)
        
        # Check recent flavor families
        recent_flavors = set()
        for day_flavors in self.flavor_family_history[-3:]:
            recent_flavors.update(day_flavors)
        
        # Calculate novelty
        overlap = candidate_flavors & recent_flavors
        if not candidate_flavors:
            return 0.5
        
        novelty = 1.0 - (len(overlap) / len(candidate_flavors))
        return novelty
    
    def _score_no_repeat_compliance(self, candidate: Recipe) -> float:
        """Check if ingredients violate no-repeat window"""
        if not self.ingredient_history:
            return 1.0
        
        candidate_ingredients = set(candidate.ingredients)
        
        # Check each day in window
        violations = 0
        for day_ingredients in self.ingredient_history:
            overlap = candidate_ingredients & day_ingredients
            violations += len(overlap)
        
        # Calculate compliance score
        max_violations = len(candidate_ingredients) * len(self.ingredient_history)
        if max_violations == 0:
            return 1.0
        
        compliance = 1.0 - (violations / max_violations)
        return compliance
    
    def check_repetition(self, candidate: Recipe, recent_recipes: List[Recipe]) -> bool:
        """
        Advanced repetition check
        Returns: True if recipe is too repetitive, False if acceptable
        """
        if not recent_recipes:
            return False
        
        # Check exact recipe repetition
        for old_recipe in recent_recipes:
            if candidate.id == old_recipe.id:
                return True
        
        # Check ingredient overlap threshold
        for old_recipe in recent_recipes:
            candidate_ing = set(candidate.ingredients)
            old_ing = set(old_recipe.ingredients)
            
            if not candidate_ing or not old_ing:
                continue
            
            overlap = candidate_ing & old_ing
            overlap_ratio = len(overlap) / len(candidate_ing)
            
            # If >70% ingredients overlap, consider it repetitive
            if overlap_ratio > 0.7:
                return True
        
        return False
    
    def calculate_variety_score(self, plan: List[Recipe]) -> float:
        """
        Calculate overall variety score for a meal plan
        """
        if not plan:
            return 0.0
        
        all_ingredients = []
        for recipe in plan:
            all_ingredients.extend(recipe.ingredients)
        
        unique_ingredients = set(all_ingredients)
        total_ingredients = len(all_ingredients)
        
        if total_ingredients == 0:
            return 1.0
        
        # Ratio of unique to total
        score = len(unique_ingredients) / total_ingredients
        return score
    
    def _analyze_textures(self, recipes: List[Recipe]) -> Dict[str, int]:
        """Analyze texture distribution in recipes"""
        texture_counts = defaultdict(int)
        
        for recipe in recipes:
            textures = self._get_recipe_textures(recipe)
            for texture in textures:
                texture_counts[texture] += 1
        
        return dict(texture_counts)
    
    def _get_recipe_textures(self, recipe: Recipe) -> Set[str]:
        """Get texture categories for a recipe"""
        textures = set()
        
        for ingredient in recipe.ingredients:
            ing_lower = ingredient.lower()
            for texture, keywords in self.TEXTURES.items():
                if any(keyword in ing_lower for keyword in keywords):
                    textures.add(texture)
        
        return textures
    
    def _analyze_flavor_families(self, recipes: List[Recipe]) -> Set[str]:
        """Analyze flavor families in recipes"""
        families = set()
        
        for recipe in recipes:
            families.update(self._get_recipe_flavor_families(recipe))
        
        return families
    
    def _get_recipe_flavor_families(self, recipe: Recipe) -> Set[str]:
        """Get flavor families for a recipe"""
        families = set()
        
        for ingredient in recipe.ingredients:
            ing_lower = ingredient.lower()
            for family, keywords in self.FLAVOR_FAMILIES.items():
                if any(keyword in ing_lower for keyword in keywords):
                    families.add(family)
        
        return families
    
    def get_ingredient_frequency_report(self) -> Dict[str, int]:
        """Get frequency report of all ingredients over time"""
        frequency = Counter()
        
        for day_ingredients in self.ingredient_history:
            frequency.update(day_ingredients)
        
        return dict(frequency.most_common())
