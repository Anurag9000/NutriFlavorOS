"""Transparent preference scoring for recipe ranking.

No neural predictor is used unless a separately validated artifact is introduced.
The current score combines explicit ingredient preferences with deterministic
flavor-profile similarity and labels missing data neutrally.
"""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict

from backend.models import Recipe, UserProfile
from backend.services.flavordb_service import FlavorDBService


class TasteEngine:
    def __init__(self):
        self.flavor_service = FlavorDBService()
        self.external_flavor_enabled = (
            os.getenv("ENABLE_EXTERNAL_FLAVOR_DATA", "false").lower() == "true"
        )
        self._ingredient_cache: Dict[str, Dict[str, float]] = {}

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _profile_for_ingredient(self, ingredient: str) -> Dict[str, float]:
        key = self._normalize(ingredient)
        if key in self._ingredient_cache:
            return self._ingredient_cache[key]
        if not self.external_flavor_enabled:
            return {}

        try:
            response = self.flavor_service.get_flavor_profile(ingredient) or {}
            profile = {
                str(name): float(value)
                for name, value in (response.get("flavor_vector", {}) or {}).items()
                if isinstance(value, (int, float))
            }
        except Exception as exc:
            print(f"Flavor lookup failed for {ingredient}: {exc}")
            profile = {}
        self._ingredient_cache[key] = profile
        return profile

    def generate_flavor_genome(self, user: UserProfile) -> Dict[str, float]:
        totals: Dict[str, float] = {}
        for ingredient, direction in [
            *((ingredient, 1.0) for ingredient in user.liked_ingredients),
            *((ingredient, -1.0) for ingredient in user.disliked_ingredients),
        ]:
            for dimension, value in self._profile_for_ingredient(ingredient).items():
                totals[dimension] = totals.get(dimension, 0.0) + value * direction

        norm = math.sqrt(sum(value * value for value in totals.values()))
        genome = {dimension: value / norm for dimension, value in totals.items()} if norm else {}
        for ingredient in user.liked_ingredients:
            genome[f"ingredient_like:{self._normalize(ingredient)}"] = 1.0
        for ingredient in user.disliked_ingredients:
            genome[f"ingredient_dislike:{self._normalize(ingredient)}"] = -1.0
        return genome

    def get_recipe_flavor_profile(self, recipe: Recipe) -> Dict[str, float]:
        if recipe.flavor_profile:
            return {
                str(name): float(value)
                for name, value in recipe.flavor_profile.items()
                if isinstance(value, (int, float))
            }

        totals: Dict[str, float] = {}
        for ingredient in recipe.ingredients:
            for dimension, value in self._profile_for_ingredient(ingredient).items():
                totals[dimension] = totals.get(dimension, 0.0) + value
        norm = math.sqrt(sum(value * value for value in totals.values()))
        return {dimension: value / norm for dimension, value in totals.items()} if norm else {}

    def predict_hedonic_score(self, recipe: Recipe, user_genome: Dict[str, float]) -> float:
        """Return a deterministic preference score in ``[0, 1]``."""

        normalized_recipe = self._normalize(" ".join([recipe.name, *recipe.ingredients]))
        liked_terms = [
            key.split(":", 1)[1]
            for key in user_genome
            if key.startswith("ingredient_like:")
        ]
        disliked_terms = [
            key.split(":", 1)[1]
            for key in user_genome
            if key.startswith("ingredient_dislike:")
        ]
        liked_hits = sum(1 for item in liked_terms if item and item in normalized_recipe)
        disliked_hits = sum(1 for item in disliked_terms if item and item in normalized_recipe)

        profile = self.get_recipe_flavor_profile(recipe)
        molecular_genome = {
            key: value
            for key, value in user_genome.items()
            if not key.startswith("ingredient_like:")
            and not key.startswith("ingredient_dislike:")
        }
        similarity = (
            self._calculate_cosine_similarity(molecular_genome, profile)
            if molecular_genome and profile
            else 0.0
        )
        molecular_component = (
            (similarity + 1.0) / 2.0 if molecular_genome and profile else 0.5
        )
        explicit_component = max(
            0.0, min(1.0, 0.5 + liked_hits * 0.2 - disliked_hits * 0.35)
        )
        return max(
            0.0,
            min(1.0, explicit_component * 0.7 + molecular_component * 0.3),
        )

    def analyze_flavor_pairing(self, ing1: str, ing2: str) -> Dict[str, Any]:
        if not self.external_flavor_enabled:
            return {
                "compatible": None,
                "similarity_score": None,
                "data_status": "disabled",
                "reason": "External flavor data is not configured",
            }
        try:
            profile1 = self._profile_for_ingredient(ing1)
            profile2 = self._profile_for_ingredient(ing2)
            similarity = self._calculate_cosine_similarity(profile1, profile2)
            return {
                "compatible": similarity >= 0.6,
                "similarity_score": similarity,
                "data_status": "external_unvalidated",
            }
        except Exception as exc:
            return {
                "compatible": None,
                "similarity_score": None,
                "data_status": "unavailable",
                "error": str(exc),
            }

    @staticmethod
    def _calculate_cosine_similarity(
        vec1: Dict[str, float], vec2: Dict[str, float]
    ) -> float:
        keys = set(vec1) | set(vec2)
        if not keys:
            return 0.0
        dot = sum(float(vec1.get(key, 0.0)) * float(vec2.get(key, 0.0)) for key in keys)
        norm1 = math.sqrt(sum(float(vec1.get(key, 0.0)) ** 2 for key in keys))
        norm2 = math.sqrt(sum(float(vec2.get(key, 0.0)) ** 2 for key in keys))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm1 * norm2)))
