
import os
import sys
import uuid
import random
from datetime import datetime
from sqlalchemy.orm import Session

# Add current directory to path so we can import from backend
sys.path.append(os.getcwd())

from backend.database import SessionLocal, DBUser, DBRecipe, init_db
from backend.models import Gender, Goal

def seed_database():
    print("Initializing database...")
    init_db()
    db: Session = SessionLocal()

    try:
        # 1. Clear existing data
        print("Clearing old data...")
        db.query(DBUser).delete()
        db.query(DBRecipe).delete()
        db.commit()

        # 2. Seed Users
        print("Seeding users...")
        users = []
        names = [
            "Alice Johnson", "Bob Smith", "Charlie Brown", "Diana Prince", "Ethan Hunt",
            "Fiona Gallagher", "George Miller", "Hannah Abbott", "Ian Wright", "Julia Roberts",
            "Kevin Hart", "Laura Palmer", "Mike Wazowski", "Nina Simone", "Oscar Isaac",
            "Paul Rudd", "Quinn Fabray", "Riley Reid", "Steve Rogers", "Tony Stark"
        ]
        
        goals = [Goal.WEIGHT_LOSS, Goal.MAINTENANCE, Goal.MUSCLE_GAIN]
        genders = [Gender.MALE, Gender.FEMALE, Gender.OTHER]
        
        dietary_restrictions_list = ["vegan", "vegetarian", "gluten-free", "dairy-free", "none"]
        health_conditions_list = ["diabetes", "hypertension", "celiac", "none"]
        
        ingredients_pool = ["chicken", "broccoli", "salmon", "spinach", "tofu", "quinoa", "beef", "avocado", "eggs", "oats", "milk", "cheese"]

        for i, name in enumerate(names):
            user_id = str(uuid.uuid4())
            goal = random.choice(goals)
            gender = random.choice(genders)
            
            # Diverse biometrics
            age = random.randint(20, 60)
            weight = random.uniform(50, 120)
            height = random.uniform(150, 200)
            activity = random.uniform(1.2, 1.9)
            
            restrictions = []
            if random.random() < 0.3:
                restrictions.append(random.choice(dietary_restrictions_list[:-1]))
                
            conditions = []
            if random.random() < 0.2:
                conditions.append(random.choice(health_conditions_list[:-1]))

            liked = random.sample(ingredients_pool, random.randint(2, 5))
            disliked = random.sample([ing for ing in ingredients_pool if ing not in liked], random.randint(1, 3))

            user = DBUser(
                id=user_id,
                name=name,
                age=age,
                weight_kg=round(weight, 1),
                height_cm=round(height, 1),
                gender=gender.value,
                activity_level=round(activity, 2),
                goal=goal.value,
                liked_ingredients=liked,
                disliked_ingredients=disliked,
                dietary_restrictions=restrictions,
                health_conditions=conditions,
                created_at=datetime.utcnow()
            )
            users.append(user)
            db.add(user)

        # 3. Seed Recipes (100+)
        print("Seeding 100+ recipes...")
        cuisines = ["Italian", "Mexican", "Japanese", "Indian", "Mediterranean", "Middle Eastern", "Chinese", "American", "Thai", "French"]
        tags_pool = ["high-protein", "low-carb", "vegan", "vegetarian", "quick", "keto", "paleo", "gluten-free"]
        
        flavor_compounds = ["vanillin", "linalool", "eugenol", "geraniol", "limonene", "cinnamaldehyde", "menthol", "pinene", "benzaldehyde", "ethanethiol"]

        for i in range(120):
            recipe_id = str(i + 1)
            cuisine = random.choice(cuisines)
            name = f"{cuisine} Style Dish {i+1}"
            
            # Detailed recipes
            ingredients = random.sample(ingredients_pool, random.randint(4, 8))
            
            # Exact macros
            calories = random.randint(300, 800)
            protein = random.randint(15, 50)
            fat = random.randint(10, 35)
            carbs = random.randint(20, 100)
            
            # Exhaustive flavor profile
            flavor_profile = {comp: round(random.uniform(0.1, 0.9), 2) for comp in random.sample(flavor_compounds, random.randint(3, 6))}
            
            tags = random.sample(tags_pool, random.randint(1, 3))
            # Ensure tags match ingredients roughly
            if "tofu" in ingredients or "quinoa" in ingredients:
                if random.random() > 0.5: tags.append("vegan")
            
            instructions = [
                f"Step 1: Prepare the {ingredients[0]}.",
                f"Step 2: Mix with {ingredients[1]}.",
                "Step 3: Cook for 15 minutes.",
                "Step 4: Serve and enjoy!"
            ]

            recipe = DBRecipe(
                id=recipe_id,
                name=name,
                description=f"A delicious {cuisine} recipe that is perfect for any occasion.",
                image_url=f"https://example.com/recipe{i+1}.jpg",
                ingredients=ingredients,
                calories=calories,
                macros={"protein": protein, "carbs": carbs, "fat": fat},
                flavor_profile=flavor_profile,
                tags=list(set(tags)),
                cuisine=cuisine,
                instructions=instructions,
                estimated_cost=round(random.uniform(3.5, 15.0), 2)
            )
            db.add(recipe)

        db.commit()
        print(f"Successfully seeded {len(names)} users and 120 recipes.")

    except Exception as e:
        print(f"Error seeding database: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
