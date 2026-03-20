# NutriFlavorOS: Database Schema and Data Contracts

This document provides an exhaustive analysis of the data formats, structures, and schemas required for the end-to-end functioning of the NutriFlavorOS app.

---

## 1. PostgreSQL Database Schema (SQLAlchemy)

The production database uses PostgreSQL (with a SQLite fallback for local development).

### Tables

#### `users`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `String` (PK) | Unique identifier (e.g., UUID or Auth0 ID) |
| `name` | `String` | User's full name |
| `age` | `Integer` | Age in years |
| `weight_kg` | `Float` | Weight in kilograms |
| `height_cm` | `Float` | Height in centimeters |
| `gender` | `String` | Enum: `male`, `female`, `other` |
| `activity_level` | `Float` | Multiplier (1.2 - 1.9) |
| `goal` | `String` | Enum: `weight_loss`, `maintenance`, `muscle_gain` |
| `liked_ingredients` | `JSON` | List of strings (e.g., `["chicken", "broccoli"]`) |
| `disliked_ingredients`| `JSON` | List of strings |
| `dietary_restrictions`| `JSON` | List of strings (e.g., `["vegan", "gluten-free"]`) |
| `health_conditions` | `JSON` | List of strings (e.g., `["diabetes", "hypertension"]`) |
| `created_at` | `DateTime`| Timestamp of account creation |

#### `recipes`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `String` (PK) | Unique identifier |
| `name` | `String` | Recipe title |
| `description` | `String` | Short description |
| `image_url` | `String` | URL to recipe image |
| `ingredients` | `JSON` | List of strings |
| `calories` | `Integer` | Total calories per serving |
| `macros` | `JSON` | Dict: `{"protein": int, "carbs": int, "fat": int}` |
| `flavor_profile` | `JSON` | Dict of molecular flavor compounds (normalized 0-1) |
| `tags` | `JSON` | List of strings (e.g., `["high-protein", "quick"]`) |
| `cuisine` | `String` | Cuisine type (e.g., `Middle Eastern`) |
| `instructions` | `JSON` | List of strings (cooking steps) |
| `estimated_cost` | `Float` | Estimated cost per serving |

#### `meal_plans`
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `Integer` (PK) | Auto-incrementing ID |
| `user_id` | `String` (FK) | Reference to `users.id` |
| `plan_data` | `JSON` | Full `PlanResponse` object (see Data Contracts) |
| `created_at` | `DateTime`| Timestamp of plan generation |

---

## 2. API Data Contracts (JSON)

### User Profile (`POST /api/v1/user`, `GET /api/v1/user/{id}`)
```json
{
  "id": "string (optional)",
  "name": "string (optional)",
  "age": "int",
  "weight_kg": "float",
  "height_cm": "float",
  "gender": "male | female | other",
  "activity_level": "float (1.2 to 1.9)",
  "goal": "weight_loss | maintenance | muscle_gain",
  "liked_ingredients": ["string"],
  "disliked_ingredients": ["string"],
  "dietary_restrictions": ["string"],
  "health_conditions": ["string"],
  "medications": ["string"],
  "target_calories": "int (optional override)",
  "target_protein_g": "int (optional override)",
  "target_carbs_g": "int (optional override)",
  "target_fat_g": "int (optional override)"
}
```

### Meal Plan Response (`GET /api/v1/meals/plan/{user_id}`)
```json
{
  "user_id": "string",
  "days": [
    {
      "day": "int",
      "meals": {
        "Breakfast": { "RecipeObject" },
        "Morning Snack": { "RecipeObject" },
        "Lunch": { "RecipeObject" },
        "Afternoon Snack": { "RecipeObject" },
        "Dinner": { "RecipeObject" }
      },
      "total_stats": {
        "calories": "float",
        "target_calories": "float",
        "carbon_footprint_kg": "float",
        "total_cost": "float"
      },
      "scores": {
        "health_match": "float (0-1)",
        "taste_match": "float (0-1)",
        "variety": "float (0-1)"
      }
    }
  ],
  "shopping_list": {
    "CategoryName": {
      "IngredientName": {
        "quantity": "string (e.g., '200g')",
        "count": "int"
      }
    }
  },
  "prep_timeline": {
    "1": ["8:00 AM - Prepare ...", "12:00 PM - Prepare ..."]
  },
  "overall_stats": {
    "average_health_match": "float",
    "average_taste_match": "float",
    "average_variety": "float",
    "total_carbon_footprint_kg": "float",
    "total_plan_cost": "float",
    "sustainability_rating": "string"
  }
}
```

---

## 3. Nested Data Structures

### A. Macros & Micros
The `NutrientTarget` model defines the daily targets.
- **Macros**: `protein_g`, `carbs_g`, `fat_g` (Integers).
- **Micros**: `micro_nutrients` (Dict mapping `string` to `float`).
  - Supported Micros (20+): `Vitamin A`, `Vitamin C`, `Vitamin D`, `Vitamin E`, `Vitamin K`, `Vitamin B1-B12`, `Folate`, `Calcium`, `Iron`, `Magnesium`, `Phosphorus`, `Potassium`, `Sodium`, `Zinc`, `Copper`, `Selenium`, `Manganese`.

### B. Flavor Profile & Flavor Genome
- **Molecular Flavor Profile**: A dictionary where keys are chemical compounds and values are normalized intensities.
  - *Example*: `{"vanillin": 0.66, "geraniol": 0.40, "eugenol": 0.62}`
- **Flavor Genome**: Created by aggregating profiles of liked/disliked ingredients, weighted by aroma thresholds.
- **Chemical Fingerprint**: Prefixed keys like `functional_terpene` or `functional_sulfur-containing`.
- **Neural Embedding (Taste Predictor)**: The `DeepTastePredictor` Transformer model hashes compound names into a **512-dimensional** tensor for high-accuracy hedonic score prediction.

### C. ML State Vector (RL Meal Planner)
The PPO agent uses a **256-dimensional** float vector:
- **Indices 0-49**: User Profile (Age, Weight, Height, Activity Level, Goal).
- **Indices 50-149**: Meal History (Recent ingredient usage, hashed into indices).
- **Indices 150-199**: Pantry Inventory (Hashed ingredient presence).
- **Indices 200-209**: Time Context (Day of week, meal slot [0, 0.5, 1.0], season).
- **Indices 210-255**: Reserved for future expansion.

---

## 4. External / Mock Data Formats

### RecipeDB (`recipes.json`)
```json
{
  "Recipe_id": "string",
  "Recipe_title": "string",
  "Calories": "float (string)",
  "Protein (g)": "float (string)",
  "Total lipid (fat) (g)": "float (string)",
  "Carbohydrate, by difference (g)": "float (string)",
  "Region": "string",
  "Ingredients": ["string"],
  "Processes": "string (|| separated)"
}
```

### FlavorDB (`flavor_db.json`)
```json
{
  "ingredient_name": {
    "category": "string",
    "flavor_vector": { "compound": "float" },
    "functional_groups": ["string"],
    "aroma_threshold": "float",
    "taste_threshold": "float"
  }
}
```

### DietRxDB (`diet_rx_db.json`)
```json
{
  "diseases": {
    "Disease Name": {
      "beneficial_foods": ["string"],
      "harmful_foods": ["string"]
    }
  }
}
```

### SustainableFoodDB (`sustainable_db.json`)
```json
{
  "ingredient_name": {
    "carbon_footprint_kg": "float",
    "water_usage_l": "float",
    "land_use_m2": "float"
  }
}
```

---

## 5. Constraints and Enums

- **Gender**: `male`, `female`, `other`.
- **Goal**: `weight_loss` (BMR - 500), `maintenance` (BMR), `muscle_gain` (BMR + 400).
- **Activity Level**: 1.2 (Sedentary) to 1.9 (Extremely Active).
- **Macro Ratios**:
  - `muscle_gain`: 35% Protein, 40% Carbs, 25% Fat.
  - `weight_loss`: 40% Protein, 30% Carbs, 30% Fat.
  - `maintenance`: 30% Protein, 35% Carbs, 35% Fat.
- **Hard Blocks**: Recipes are strictly filtered out if they contain `disliked_ingredients` or keywords associated with `dietary_restrictions` (e.g., "chicken" for vegetarians).
- **Medical Safety**: `DietRxDB` provides a hard-block shield for health conditions and drug-food interactions.
