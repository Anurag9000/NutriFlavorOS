"""Restriction-aware culinary substitution baseline.

Suggestions preserve culinary role where possible. They are not allergy or
medical guarantees; packaged-product labels and cross-contact warnings must be
verified by the user.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set

from pydantic import BaseModel, Field

from backend.domain.ingredients import canonicalize_ingredient_name


class SubstitutionCandidate(BaseModel):
    ingredient: str
    replacement: str
    role: str
    ratio: Optional[float] = Field(default=None, gt=0)
    score: float = Field(ge=0, le=1)
    reasons: List[str]
    warnings: List[str]


_RULES: Dict[str, List[Dict[str, object]]] = {
    "milk": [
        {"target": "oat milk", "role": "liquid dairy replacement", "ratio": 1.0, "tags": {"vegan", "dairy-free"}},
        {"target": "soy milk", "role": "liquid dairy replacement", "ratio": 1.0, "tags": {"vegan", "dairy-free", "soy"}},
        {"target": "coconut milk", "role": "rich liquid dairy replacement", "ratio": 1.0, "tags": {"vegan", "dairy-free", "coconut"}},
    ],
    "butter": [
        {"target": "plant butter", "role": "solid fat", "ratio": 1.0, "tags": {"vegan", "dairy-free"}},
        {"target": "olive oil", "role": "cooking fat", "ratio": 0.75, "tags": {"vegan", "dairy-free"}, "warning": "Not a universal one-to-one baking substitute."},
    ],
    "egg": [
        {"target": "flax egg", "role": "binder", "ratio": 1.0, "tags": {"vegan", "egg-free"}, "warning": "Suitable mainly for binding, not for every aeration or custard function."},
        {"target": "aquafaba", "role": "foaming and binding", "ratio": None, "tags": {"vegan", "egg-free"}, "warning": "Recipe-specific quantity testing is required."},
    ],
    "wheat flour": [
        {"target": "certified gluten-free flour blend", "role": "flour structure", "ratio": 1.0, "tags": {"gluten-free"}, "warning": "Verify certification and recipe-specific binder needs."},
        {"target": "rice flour", "role": "flour component", "ratio": None, "tags": {"gluten-free"}, "warning": "Texture differs and a blend may be required."},
    ],
    "chicken": [
        {"target": "tofu", "role": "protein component", "ratio": 1.0, "tags": {"vegetarian", "vegan", "soy"}},
        {"target": "chickpeas", "role": "protein and bulk", "ratio": 1.0, "tags": {"vegetarian", "vegan", "legume"}},
        {"target": "tempeh", "role": "firm protein component", "ratio": 1.0, "tags": {"vegetarian", "vegan", "soy"}},
    ],
    "beef": [
        {"target": "lentils", "role": "protein and bulk", "ratio": 1.0, "tags": {"vegetarian", "vegan", "legume"}},
        {"target": "mushrooms", "role": "savory bulk", "ratio": 1.0, "tags": {"vegetarian", "vegan"}},
        {"target": "tofu", "role": "protein component", "ratio": 1.0, "tags": {"vegetarian", "vegan", "soy"}},
    ],
    "yogurt": [
        {"target": "unsweetened plant yogurt", "role": "cultured creamy component", "ratio": 1.0, "tags": {"vegan", "dairy-free"}},
    ],
    "cream": [
        {"target": "coconut cream", "role": "rich creamy component", "ratio": 1.0, "tags": {"vegan", "dairy-free", "coconut"}},
        {"target": "cashew cream", "role": "rich creamy component", "ratio": 1.0, "tags": {"vegan", "dairy-free", "tree nut"}},
    ],
    "honey": [
        {"target": "maple syrup", "role": "liquid sweetener", "ratio": 1.0, "tags": {"vegan"}},
    ],
    "breadcrumbs": [
        {"target": "certified gluten-free breadcrumbs", "role": "coating or binder", "ratio": 1.0, "tags": {"gluten-free"}},
        {"target": "ground certified gluten-free oats", "role": "binder", "ratio": None, "tags": {"gluten-free"}, "warning": "Use only certified gluten-free oats when required."},
    ],
    "peanut butter": [
        {"target": "sunflower seed butter", "role": "seed or nut spread", "ratio": 1.0, "tags": {"peanut-free", "seed"}, "warning": "Verify facility cross-contact and other seed allergies."},
    ],
    "soy sauce": [
        {"target": "certified gluten-free tamari", "role": "salty fermented seasoning", "ratio": 1.0, "tags": {"gluten-free", "soy"}, "warning": "Tamari may still contain soy and must be certified gluten-free."},
        {"target": "coconut aminos", "role": "salty-sweet seasoning", "ratio": 1.0, "tags": {"soy-free", "gluten-free", "coconut"}, "warning": "Flavor and sodium differ from soy sauce."},
    ],
}


def _normal_set(values: List[str]) -> Set[str]:
    return {canonicalize_ingredient_name(value) for value in values if canonicalize_ingredient_name(value)}


def suggest_substitutions(
    ingredient: str,
    *,
    allergies: List[str],
    dietary_restrictions: List[str],
    pantry_ingredients: Optional[List[str]] = None,
    limit: int = 5,
) -> List[SubstitutionCandidate]:
    source = canonicalize_ingredient_name(ingredient)
    allergy_terms = _normal_set(allergies)
    restrictions = _normal_set(dietary_restrictions)
    pantry = _normal_set(pantry_ingredients or [])
    candidates = []
    for rule in _RULES.get(source, []):
        target = canonicalize_ingredient_name(str(rule["target"]))
        tags = {canonicalize_ingredient_name(str(value)) for value in rule.get("tags", set())}
        if any(term and (term == target or term in target or term in tags) for term in allergy_terms):
            continue
        if "vegan" in restrictions and "vegan" not in tags:
            continue
        if "vegetarian" in restrictions and not ({"vegetarian", "vegan"} & tags):
            continue
        if "gluten free" in restrictions and "gluten free" not in tags:
            continue
        if "dairy free" in restrictions and "dairy free" not in tags:
            continue
        score = 0.65
        reasons = [f"Preserves the culinary role: {rule['role']}"]
        if target in pantry:
            score += 0.2
            reasons.append("Already available in pantry")
        if restrictions & tags:
            score += 0.1
            reasons.append("Matches an active dietary restriction")
        warnings = [
            "Verify packaged-product labels and cross-contact warnings before use.",
            "This is a culinary suggestion, not an allergy or medical guarantee.",
        ]
        if rule.get("warning"):
            warnings.append(str(rule["warning"]))
        candidates.append(
            SubstitutionCandidate(
                ingredient=source,
                replacement=target,
                role=str(rule["role"]),
                ratio=float(rule["ratio"]) if rule.get("ratio") is not None else None,
                score=min(1.0, score),
                reasons=reasons,
                warnings=warnings,
            )
        )
    return sorted(candidates, key=lambda value: (-value.score, value.replacement))[: max(1, min(limit, 20))]
