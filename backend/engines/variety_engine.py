"""Deterministic variety scoring with canonical ingredient comparisons."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Dict, List, Set

from backend.models import Recipe


class VarietyEngine:
    TEXTURES = {
        "crunchy": ("nut", "cracker", "chip", "raw vegetable", "toast"),
        "creamy": ("yogurt", "cheese", "avocado", "hummus", "sauce"),
        "soft": ("banana", "tofu", "pasta", "rice", "bread"),
        "chewy": ("meat", "dried fruit", "caramel", "jerky"),
        "liquid": ("soup", "smoothie", "juice", "broth"),
    }
    FLAVOR_FAMILIES = {
        "aromatic": ("garlic", "onion", "ginger", "herb"),
        "citrus": ("lemon", "lime", "orange", "grapefruit"),
        "earthy": ("mushroom", "beet", "potato", "carrot"),
        "sweet": ("honey", "maple", "sugar", "fruit"),
        "savory": ("soy sauce", "miso", "cheese", "meat"),
    }

    def __init__(self, no_repeat_window: int = 7):
        if no_repeat_window < 1:
            raise ValueError("no_repeat_window must be at least 1")
        self.no_repeat_window = no_repeat_window
        self.ingredient_history: List[Set[str]] = []
        self.cuisine_history: List[str] = []
        self.texture_history: List[Dict[str, int]] = []
        self.flavor_family_history: List[Set[str]] = []

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    @classmethod
    def _ingredient_set(cls, recipe: Recipe) -> Set[str]:
        values = (
            [line.name for line in recipe.ingredient_lines if line.name]
            if recipe.ingredient_lines
            else recipe.ingredients
        )
        return {cls._normalize(item) for item in values if cls._normalize(item)}

    def update_history(self, recipes: List[Recipe], cuisine: str) -> None:
        ingredients = set().union(*(self._ingredient_set(recipe) for recipe in recipes)) if recipes else set()
        self.ingredient_history.append(ingredients)
        self.cuisine_history.append(self._normalize(cuisine) or "unknown")
        self.texture_history.append(self._analyze_textures(recipes))
        self.flavor_family_history.append(self._analyze_flavor_families(recipes))

        for history in (
            self.ingredient_history,
            self.cuisine_history,
            self.texture_history,
            self.flavor_family_history,
        ):
            del history[:-self.no_repeat_window]

    def score_variety(self, candidate: Recipe, recent_recipes: List[Recipe]) -> float:
        return (
            self._score_ingredient_uniqueness(candidate, recent_recipes) * 0.30
            + self._score_cuisine_diversity(candidate) * 0.25
            + self._score_texture_balance(candidate) * 0.20
            + self._score_flavor_rotation(candidate) * 0.15
            + self._score_no_repeat_compliance(candidate) * 0.10
        )

    def _score_ingredient_uniqueness(self, candidate: Recipe, recent_recipes: List[Recipe]) -> float:
        candidate_ingredients = self._ingredient_set(candidate)
        if not candidate_ingredients:
            return 0.0
        recent = set().union(*(self._ingredient_set(recipe) for recipe in recent_recipes)) if recent_recipes else set()
        return 1.0 - len(candidate_ingredients & recent) / len(candidate_ingredients)

    def _score_cuisine_diversity(self, candidate: Recipe) -> float:
        recent = self.cuisine_history[-self.no_repeat_window :]
        if not recent:
            return 1.0
        cuisine = self._normalize(candidate.cuisine or "unknown") or "unknown"
        return max(0.0, 1.0 - Counter(recent)[cuisine] / len(recent))

    def _score_texture_balance(self, candidate: Recipe) -> float:
        candidate_textures = self._get_recipe_textures(candidate)
        if not candidate_textures or not self.texture_history:
            return 0.5 if not candidate_textures else 1.0
        counts: Counter[str] = Counter()
        for day in self.texture_history[-3:]:
            counts.update(day)
        maximum = max(1, sum(counts.values()))
        penalty = sum(counts[texture] / maximum for texture in candidate_textures) / len(candidate_textures)
        return max(0.0, 1.0 - penalty)

    def _score_flavor_rotation(self, candidate: Recipe) -> float:
        candidate_families = self._get_recipe_flavor_families(candidate)
        if not candidate_families:
            return 0.5
        recent = set().union(*self.flavor_family_history[-3:]) if self.flavor_family_history else set()
        return 1.0 - len(candidate_families & recent) / len(candidate_families)

    def _score_no_repeat_compliance(self, candidate: Recipe) -> float:
        ingredients = self._ingredient_set(candidate)
        if not ingredients:
            return 0.0
        recent = set().union(*self.ingredient_history) if self.ingredient_history else set()
        return 1.0 - len(ingredients & recent) / len(ingredients)

    def check_repetition(self, candidate: Recipe, recent_recipes: List[Recipe]) -> bool:
        candidate_ingredients = self._ingredient_set(candidate)
        for old_recipe in recent_recipes:
            if candidate.id == old_recipe.id:
                return True
            old_ingredients = self._ingredient_set(old_recipe)
            union = candidate_ingredients | old_ingredients
            if union and len(candidate_ingredients & old_ingredients) / len(union) > 0.70:
                return True
        return False

    def calculate_variety_score(self, plan: List[Recipe]) -> float:
        if not plan:
            return 0.0
        ingredients = [item for recipe in plan for item in self._ingredient_set(recipe)]
        if not ingredients:
            return 0.0
        return len(set(ingredients)) / len(ingredients)

    def _analyze_textures(self, recipes: List[Recipe]) -> Dict[str, int]:
        counts: Dict[str, int] = defaultdict(int)
        for recipe in recipes:
            for texture in self._get_recipe_textures(recipe):
                counts[texture] += 1
        return dict(counts)

    def _get_recipe_textures(self, recipe: Recipe) -> Set[str]:
        text = " ".join(self._ingredient_set(recipe))
        return {
            texture
            for texture, keywords in self.TEXTURES.items()
            if any(keyword in text for keyword in keywords)
        }

    def _analyze_flavor_families(self, recipes: List[Recipe]) -> Set[str]:
        families: Set[str] = set()
        for recipe in recipes:
            families.update(self._get_recipe_flavor_families(recipe))
        return families

    def _get_recipe_flavor_families(self, recipe: Recipe) -> Set[str]:
        text = " ".join(self._ingredient_set(recipe))
        return {
            family
            for family, keywords in self.FLAVOR_FAMILIES.items()
            if any(keyword in text for keyword in keywords)
        }

    def get_ingredient_frequency_report(self) -> Dict[str, int]:
        counts: Counter[str] = Counter()
        for day in self.ingredient_history:
            counts.update(day)
        return dict(counts.most_common())
