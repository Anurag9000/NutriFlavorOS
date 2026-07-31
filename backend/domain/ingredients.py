"""Quantity-aware ingredient parsing and normalization.

The parser is deliberately conservative. It converts only units with safe,
well-defined dimensional relationships and preserves ranges and unknown units
rather than inventing precision.
"""

from __future__ import annotations

import re
from fractions import Fraction
from typing import Dict, Iterable, Optional, Tuple

from backend.models import IngredientLine, IngredientParseStatus


_UNICODE_FRACTIONS: Dict[str, str] = {
    "¼": "1/4",
    "½": "1/2",
    "¾": "3/4",
    "⅐": "1/7",
    "⅑": "1/9",
    "⅒": "1/10",
    "⅓": "1/3",
    "⅔": "2/3",
    "⅕": "1/5",
    "⅖": "2/5",
    "⅗": "3/5",
    "⅘": "4/5",
    "⅙": "1/6",
    "⅚": "5/6",
    "⅛": "1/8",
    "⅜": "3/8",
    "⅝": "5/8",
    "⅞": "7/8",
}

# alias -> (display unit, canonical unit, multiplier)
_UNIT_ALIASES: Dict[str, Tuple[str, str, float]] = {
    "g": ("g", "g", 1.0),
    "gram": ("g", "g", 1.0),
    "grams": ("g", "g", 1.0),
    "kg": ("kg", "g", 1000.0),
    "kilogram": ("kg", "g", 1000.0),
    "kilograms": ("kg", "g", 1000.0),
    "mg": ("mg", "g", 0.001),
    "milligram": ("mg", "g", 0.001),
    "milligrams": ("mg", "g", 0.001),
    "oz": ("oz", "g", 28.349523125),
    "ounce": ("oz", "g", 28.349523125),
    "ounces": ("oz", "g", 28.349523125),
    "lb": ("lb", "g", 453.59237),
    "lbs": ("lb", "g", 453.59237),
    "pound": ("lb", "g", 453.59237),
    "pounds": ("lb", "g", 453.59237),
    "ml": ("ml", "ml", 1.0),
    "milliliter": ("ml", "ml", 1.0),
    "milliliters": ("ml", "ml", 1.0),
    "millilitre": ("ml", "ml", 1.0),
    "millilitres": ("ml", "ml", 1.0),
    "l": ("l", "ml", 1000.0),
    "liter": ("l", "ml", 1000.0),
    "liters": ("l", "ml", 1000.0),
    "litre": ("l", "ml", 1000.0),
    "litres": ("l", "ml", 1000.0),
    "tsp": ("tsp", "ml", 4.92892159375),
    "teaspoon": ("tsp", "ml", 4.92892159375),
    "teaspoons": ("tsp", "ml", 4.92892159375),
    "tbsp": ("tbsp", "ml", 14.78676478125),
    "tablespoon": ("tbsp", "ml", 14.78676478125),
    "tablespoons": ("tbsp", "ml", 14.78676478125),
    "cup": ("cup", "ml", 236.5882365),
    "cups": ("cup", "ml", 236.5882365),
    "fl oz": ("fl oz", "ml", 29.5735295625),
    "fluid ounce": ("fl oz", "ml", 29.5735295625),
    "fluid ounces": ("fl oz", "ml", 29.5735295625),
    "count": ("count", "count", 1.0),
    "unit": ("count", "count", 1.0),
    "units": ("count", "count", 1.0),
    "each": ("count", "count", 1.0),
    "piece": ("piece", "piece", 1.0),
    "pieces": ("piece", "piece", 1.0),
    "slice": ("slice", "slice", 1.0),
    "slices": ("slice", "slice", 1.0),
    "clove": ("clove", "clove", 1.0),
    "cloves": ("clove", "clove", 1.0),
    "can": ("can", "can", 1.0),
    "cans": ("can", "can", 1.0),
    "package": ("package", "package", 1.0),
    "packages": ("package", "package", 1.0),
    "packet": ("packet", "packet", 1.0),
    "packets": ("packet", "packet", 1.0),
    "bunch": ("bunch", "bunch", 1.0),
    "bunches": ("bunch", "bunch", 1.0),
    "sprig": ("sprig", "sprig", 1.0),
    "sprigs": ("sprig", "sprig", 1.0),
    "stalk": ("stalk", "stalk", 1.0),
    "stalks": ("stalk", "stalk", 1.0),
    "head": ("head", "head", 1.0),
    "heads": ("head", "head", 1.0),
    "pinch": ("pinch", "pinch", 1.0),
    "pinches": ("pinch", "pinch", 1.0),
}

_PREPARATION_TOKENS = {
    "about",
    "approximately",
    "chopped",
    "diced",
    "finely",
    "fresh",
    "large",
    "medium",
    "minced",
    "optional",
    "peeled",
    "roughly",
    "small",
    "sliced",
    "thinly",
    "to",
    "taste",
}

_NAME_ALIASES = {
    "eggs": "egg",
    "tomatoes": "tomato",
    "potatoes": "potato",
    "chilies": "chili",
    "chillies": "chili",
    "cloves garlic": "garlic",
    "clove garlic": "garlic",
}

_NUMBER_PATTERN = r"(?:\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)"
_UNIT_PATTERN = "|".join(
    re.escape(unit) for unit in sorted(_UNIT_ALIASES, key=len, reverse=True)
)
_LINE_PATTERN = re.compile(
    rf"^\s*(?P<q1>{_NUMBER_PATTERN})"
    rf"(?:\s*(?:-|–|—|to)\s*(?P<q2>{_NUMBER_PATTERN}))?"
    rf"(?:\s*(?P<unit>{_UNIT_PATTERN})\b)?"
    rf"\s*(?P<name>.*)$",
    re.IGNORECASE,
)


def _replace_unicode_fractions(value: str) -> str:
    normalized = value
    for glyph, fraction in _UNICODE_FRACTIONS.items():
        normalized = re.sub(rf"(?<=\d){re.escape(glyph)}", f" {fraction}", normalized)
        normalized = normalized.replace(glyph, fraction)
    return normalized


def _parse_number(value: str) -> float:
    value = value.strip()
    if " " in value and "/" in value:
        whole, fraction = value.split(None, 1)
        return float(whole) + float(Fraction(fraction))
    if "/" in value:
        return float(Fraction(value))
    return float(value)


def canonicalize_ingredient_name(value: str) -> str:
    """Return a conservative comparison key for an ingredient name."""

    name = value.lower().strip()
    name = re.sub(r"\([^)]*\)", " ", name)
    name = re.split(r"[,;]", name, maxsplit=1)[0]
    name = re.sub(r"^of\s+", "", name)
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", name)
        if token not in _PREPARATION_TOKENS
    ]
    canonical = " ".join(tokens).strip()
    return _NAME_ALIASES.get(canonical, canonical)


def parse_ingredient_line(raw: str) -> IngredientLine:
    """Parse one ingredient statement without inventing unavailable quantities."""

    original = str(raw or "").strip()
    if not original:
        return IngredientLine(raw="", name="", parse_status=IngredientParseStatus.UNQUANTIFIED)

    normalized = _replace_unicode_fractions(original)
    match = _LINE_PATTERN.match(normalized)
    if match is None:
        return IngredientLine(
            raw=original,
            name=canonicalize_ingredient_name(original),
            parse_status=IngredientParseStatus.UNQUANTIFIED,
        )

    q1 = _parse_number(match.group("q1"))
    q2 = _parse_number(match.group("q2")) if match.group("q2") else q1
    quantity_min, quantity_max = sorted((q1, q2))
    raw_unit = match.group("unit")
    name = canonicalize_ingredient_name(match.group("name"))

    if not name:
        name = canonicalize_ingredient_name(original)

    if raw_unit:
        display_unit, canonical_unit, multiplier = _UNIT_ALIASES[raw_unit.lower()]
        return IngredientLine(
            raw=original,
            name=name,
            quantity_min=quantity_min,
            quantity_max=quantity_max,
            unit=display_unit,
            canonical_quantity_min=quantity_min * multiplier,
            canonical_quantity_max=quantity_max * multiplier,
            canonical_unit=canonical_unit,
            parse_status=IngredientParseStatus.NORMALIZED,
        )

    return IngredientLine(
        raw=original,
        name=name,
        quantity_min=quantity_min,
        quantity_max=quantity_max,
        unit="count",
        canonical_quantity_min=quantity_min,
        canonical_quantity_max=quantity_max,
        canonical_unit="count",
        parse_status=IngredientParseStatus.PARTIAL,
    )


def parse_ingredient_lines(values: Iterable[str]) -> list[IngredientLine]:
    return [parse_ingredient_line(value) for value in values]


def scale_quantity_range(
    line: IngredientLine,
    factor: float,
) -> Tuple[Optional[float], Optional[float], Optional[str]]:
    """Scale a parsed canonical range for consumed servings."""

    if factor < 0:
        raise ValueError("ingredient scale factor cannot be negative")
    if line.canonical_quantity_min is None or line.canonical_quantity_max is None:
        return None, None, line.canonical_unit
    return (
        line.canonical_quantity_min * factor,
        line.canonical_quantity_max * factor,
        line.canonical_unit,
    )
