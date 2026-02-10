import json
import random
import os
from datetime import datetime

# Configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "backend", "data")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------
# 1. FlavorDB Generation (Ingredients & Molecular Data)
# ---------------------------------------------------------
print("Generating FlavorDB data...")

COMMON_INGREDIENTS = [
    "chicken breast", "salmon fillet", "beef steak", "tofu", "chickpeas",
    "brown rice", "quinoa", "sweet potato", "spinach", "kale",
    "broccoli", "avocado", "almonds", "walnuts", "olive oil",
    "garlic", "onion", "ginger", "lemon", "basil",
    "tomato", "bell pepper", "carrot", "cucumber", "yogurt",
    "cheese", "milk", "egg", "honey", "soy sauce",
    "cumin", "turmeric", "black pepper", "cinnamon", "vanilla"
]

FUNCTIONAL_GROUPS = [
    "alcohol", "aldehyde", "ketone", "ester", "terpene", 
    "phenolic", "sulfur-containing", "acid", "lactone"
]

FLAVOR_COMPOUNDS = [
    "limonene", "pinene", "eugenol", "vanillin", "cinnamaldehyde",
    "menthol", "geraniol", "linalool", "benzaldehyde", "ethanethiol"
]

flavor_db = {}

for ing in COMMON_INGREDIENTS:
    # Generate realistic molecular data
    flavor_db[ing] = {
        "ingredient": ing,
        "category": "vegetable" if ing in ["spinach", "kale", "broccoli"] else "protein" if ing in ["chicken breast", "salmon fillet"] else "other",
        "flavor_vector": {
            cmp: round(random.uniform(0.01, 0.99), 4) 
            for cmp in random.sample(FLAVOR_COMPOUNDS, k=random.randint(3, 8))
        },
        "functional_groups": random.sample(FUNCTIONAL_GROUPS, k=random.randint(1, 3)),
        "aroma_threshold": round(random.uniform(0.1, 5.0), 2),  # Lower is stronger
        "taste_threshold": round(random.uniform(0.5, 10.0), 2),
        "molecular_properties": {
            "weight": round(random.uniform(50, 500), 2),
            "alogp": round(random.uniform(-2, 5), 2),  # Lipophilicity
            "hbd_count": random.randint(0, 5),
            "hba_count": random.randint(1, 10)
        },
        "natural_occurrence": True,
        "safety_approvals": {"fema": True, "jecfa": True, "efsa": True}
    }

with open(os.path.join(DATA_DIR, "flavor_db.json"), "w") as f:
    json.dump(flavor_db, f, indent=2)

# ---------------------------------------------------------
# 2. RecipeDB Generation (Recipes with Nutrition)
# ---------------------------------------------------------
print("Generating RecipeDB data...")

CUISINES = ["Mediterranean", "Asian", "Mexican", "Italian", "American", "Indian"]
DIET_TYPES = ["Vegan", "Vegetarian", "Keto", "Paleo", "Gluten-Free"]
COOKING_METHODS = ["Baking", "Grilling", "Sautéing", "Boiling", "Roasting"]

recipes = []

for i in range(1, 61):  # Generate 60 recipes
    cuisine = random.choice(CUISINES)
    base_ing = random.choice(COMMON_INGREDIENTS)
    secondary_ing = random.choice([ing for ing in COMMON_INGREDIENTS if ing != base_ing])
    
    recipe_name = f"{cuisine} {base_ing.title()} with {secondary_ing.title()}"
    
    # Nutrition logic
    calories = random.randint(250, 800)
    protein = random.randint(10, 50)
    fat = random.randint(5, 40)
    carbs = (calories - (protein * 4 + fat * 9)) // 4
    carbs = max(5, carbs)
    
    # Ingredients list (subset of flavor db)
    num_ingredients = random.randint(4, 10)
    recipe_ingredients = list(set([base_ing, secondary_ing] + random.sample(COMMON_INGREDIENTS, k=num_ingredients-2)))
    
    recipe = {
        "id": str(i),
        # External API fields (for Services)
        "title": recipe_name,
        "image": f"https://example.com/recipe_{i}.jpg",
        "cuisines": [cuisine],
        "diets": random.sample(DIET_TYPES, k=random.randint(0, 2)),
        "instructions": [
            f"Prepare the {base_ing}.",
            f"Mix with {secondary_ing}.",
            f"Cook using {random.choice(COOKING_METHODS)} method for {random.randint(10, 30)} minutes.",
            "Serve hot and enjoy!"
        ],
        "nutrition": { 
            "calories": calories,
            "protein": f"{protein}g",
            "fat": f"{fat}g",
            "carbohydrates": f"{carbs}g",
            "sugar": f"{random.randint(1, 15)}g",
            "fiber": f"{random.randint(1, 10)}g",
            "sodium": f"{random.randint(100, 800)}mg"
        },
        "micronutrients": {
            "Vitamin A": random.randint(0, 100),
            "Vitamin C": random.randint(0, 100),
            "Calcium": random.randint(0, 50),
            "Iron": random.randint(0, 50)
        },
        "ingredients": recipe_ingredients,
        "aggregatedFlavorProfile": {
            "bitter": random.random(),
            "sour": random.random(),
            "sweet": random.random(),
            "salty": random.random(),
            "umami": random.random()
        },
        
        # Internal Model fields (for PlanGenerator/Frontend)
        "name": recipe_name,
        "description": f"A delicious {cuisine} dish made with {base_ing}.",
        "image_url": f"https://example.com/recipe_{i}.jpg",
        "cuisine": cuisine,
        "calories": calories,
        "macros": {
            "protein": protein,
            "fat": fat,
            "carbohydrates": carbs
        },
        "flavor_profile": {
            "bitter": random.random(),
            "sour": random.random(),
            "sweet": random.random(),
            "salty": random.random(),
            "umami": random.random()
        },
        "tags": [cuisine, "Healthy"],
        "readyInMinutes": random.randint(15, 60),
        "servings": random.randint(1, 4)
    }
    recipes.append(recipe)

with open(os.path.join(DATA_DIR, "recipes.json"), "w") as f:
    json.dump(recipes, f, indent=2)

# ---------------------------------------------------------
# 3. DietRxDB Generation (Diseases & Interactions)
# ---------------------------------------------------------
print("Generating DietRxDB data...")

DISEASES = [
    "Diabetes Type 2", "Hypertension", "Celiac Disease", 
    "Acid Reflux", "High Cholesterol", "Gout"
]

diet_rx = {}

for disease in DISEASES:
    # Randomly assign beneficial and harmful foods
    shuffled_ings = list(COMMON_INGREDIENTS)
    random.shuffle(shuffled_ings)
    
    beneficial = shuffled_ings[:5]
    harmful = shuffled_ings[5:10]
    
    diet_rx[disease] = {
        "name": disease,
        "description": f"Chronic condition affecting metabolic health.",
        "beneficial_foods": beneficial,
        "harmful_foods": harmful,
        "publications": random.randint(5, 50)
    }

# Drug interactions
drug_interactions = {}
for ing in COMMON_INGREDIENTS:
    if random.random() < 0.2:  # 20% chance of interaction
        drug_interactions[ing] = [
            {
                "drug": "Warfarin" if ing in ["spinach", "kale"] else "Metformin",
                "severity": "High" if ing in ["grapefruit"] else "Moderate",
                "effect": "Altered absorption or metabolism."
            }
        ]

with open(os.path.join(DATA_DIR, "diet_rx_db.json"), "w") as f:
    json.dump({"diseases": diet_rx, "interactions": drug_interactions}, f, indent=2)

# ---------------------------------------------------------
# 4. SustainableFoodDB Generation (Carbon Footprint)
# ---------------------------------------------------------
print("Generating SustainableFoodDB data...")

sustainable_db = {}

for ing in COMMON_INGREDIENTS:
    # Assign realistic relative footprints
    if ing in ["beef steak"]:
        base_cf = 27.0
    elif ing in ["pork", "cheese"]:
        base_cf = 12.0
    elif ing in ["chicken breast", "salmon fillet"]:
        base_cf = 6.9
    elif ing in ["milk", "eggs", "yogurt"]:
        base_cf = 3.0
    elif ing in ["rice", "tofu", "almonds"]:
        base_cf = 2.0
    else: # Vegetables, grains
        base_cf = 0.5
        
    # Add variation
    cf = round(base_cf * random.uniform(0.8, 1.2), 2)
    
    sustainable_db[ing] = {
        "carbon_footprint_kg": cf,
        "water_usage_l": round(cf * 500, 0), # Rough correlation
        "land_use_m2": round(cf * 5, 1)
    }

with open(os.path.join(DATA_DIR, "sustainable_db.json"), "w") as f:
    json.dump(sustainable_db, f, indent=2)

print("✅ Mock data generation complete!")
