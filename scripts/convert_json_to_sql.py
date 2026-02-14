import json
import os
import datetime

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "backend", "data")
OUTPUT_FILE = os.path.join(DATA_DIR, "mock_data.sql")

def escape_sql(value):
    if value is None:
        return "NULL"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list)):
        return "'" + json.dumps(value).replace("'", "''") + "'"
    return "'" + str(value).replace("'", "''") + "'"

def generate_sql():
    sql = []
    sql.append("-- Mock Data Dump generated on " + str(datetime.datetime.now()))
    sql.append("BEGIN TRANSACTION;")
    
    # 1. Recipes
    recipes_path = os.path.join(DATA_DIR, "recipes.json")
    if os.path.exists(recipes_path):
        print("Processing Recipes...")
        with open(recipes_path, 'r') as f:
            recipes = json.load(f)
        
        sql.append("\n-- Table: recipes")
        sql.append("CREATE TABLE IF NOT EXISTS recipes (id TEXT PRIMARY KEY, title TEXT, image TEXT, readyInMinutes INTEGER, servings INTEGER, sourceUrl TEXT, nutrition TEXT, cuisines TEXT, diets TEXT, instructions TEXT);")
        
        for r in recipes:
            # Handle RecipeDB V2 keys vs Old Mock keys
            r_id = r.get("Recipe_id") or r.get("id")
            title = r.get("Recipe_title") or r.get("title")
            image = r.get("image") # Likely missing in harvest, could construct URL if needed
            
            # Time
            ready_time = r.get("total_time") or r.get("readyInMinutes")
            
            # Nutrition Construction
            nutrition = r.get("nutrition")
            if not nutrition and "Calories" in r:
                nutrition = {
                    "calories": r.get("Calories"),
                    "protein": r.get("Protein (g)"),
                    "fat": r.get("Total lipid (fat) (g)"),
                    "carbs": r.get("Carbohydrate, by difference (g)")
                }
            
            # Cuisines
            cuisines = r.get("cuisines")
            if not cuisines and "Region" in r:
                cuisines = [x for x in [r.get("Region"), r.get("Sub_region")] if x]
                
            # Diets
            diets = r.get("diets", [])
            # If diets is list (old mock), fine. If missing, infer.
            if not diets or not isinstance(diets, list):
                diets = []
                if r.get("vegan") == "1.0": diets.append("vegan")
                if r.get("pescetarian") == "1.0": diets.append("pescetarian")
                if r.get("lacto_vegetarian") == "1.0": diets.append("lacto-vegetarian")
                if r.get("ovo_vegetarian") == "1.0": diets.append("ovo-vegetarian")
            
            # Instructions: "process1||process2" -> list
            instructions = r.get("instructions")
            if not instructions and "Processes" in r:
                instructions = r["Processes"].split("||") if r["Processes"] else []
            elif isinstance(instructions, str):
                instructions = [instructions]
                
            cols = ["id", "title", "image", "readyInMinutes", "servings", "sourceUrl", "nutrition", "cuisines", "diets", "instructions"]
            vals = [
                escape_sql(r_id),
                escape_sql(title),
                escape_sql(image),
                escape_sql(ready_time),
                escape_sql(r.get("servings")),
                escape_sql(r.get("Source") or r.get("sourceUrl")),
                escape_sql(json.dumps(nutrition or {})),
                escape_sql(json.dumps(cuisines or [])),
                escape_sql(json.dumps(diets or [])),
                escape_sql(json.dumps(instructions or []))
            ]
            sql.append(f"INSERT OR REPLACE INTO recipes ({', '.join(cols)}) VALUES ({', '.join(vals)});")

    # 2. FlavorDB
    flavor_path = os.path.join(DATA_DIR, "flavor_db.json")
    if os.path.exists(flavor_path):
        print("Processing FlavorDB...")
        with open(flavor_path, 'r') as f:
            flavors = json.load(f)
            
        sql.append("\n-- Table: flavor_profiles")
        sql.append("CREATE TABLE IF NOT EXISTS flavor_profiles (ingredient TEXT PRIMARY KEY, category TEXT, flavor_profile TEXT, functional_groups TEXT, natural_occurrence TEXT);")
        
        for name, data in flavors.items():
            cols = ["ingredient", "category", "flavor_profile", "functional_groups", "natural_occurrence"]
            vals = [
                escape_sql(name),
                escape_sql(data.get("category")),
                escape_sql(json.dumps(data.get("flavor_profile", {}))),
                escape_sql(json.dumps(data.get("functional_groups", []))),
                escape_sql(str(data.get("natural_occurrence", "")))
            ]
            sql.append(f"INSERT OR REPLACE INTO flavor_profiles ({', '.join(cols)}) VALUES ({', '.join(vals)});")

    # 3. SustainableDB
    sust_path = os.path.join(DATA_DIR, "sustainable_db.json")
    if os.path.exists(sust_path):
        print("Processing SustainableDB...")
        with open(sust_path, 'r') as f:
            sust = json.load(f)
            
        sql.append("\n-- Table: sustainability")
        sql.append("CREATE TABLE IF NOT EXISTS sustainability (food_item TEXT PRIMARY KEY, carbon_footprint_kg REAL, water_usage_l REAL, land_use_m2 REAL);")
        
        for name, data in sust.items():
            cols = ["food_item", "carbon_footprint_kg", "water_usage_l", "land_use_m2"]
            vals = [
                escape_sql(name),
                escape_sql(data.get("carbon_footprint_kg")),
                escape_sql(data.get("water_usage_l")),
                escape_sql(data.get("land_use_m2"))
            ]
            sql.append(f"INSERT OR REPLACE INTO sustainability ({', '.join(cols)}) VALUES ({', '.join(vals)});")

    # 4. DietRxDB
    diet_path = os.path.join(DATA_DIR, "diet_rx_db.json")
    if os.path.exists(diet_path):
        print("Processing DietRxDB...")
        with open(diet_path, 'r') as f:
            diet = json.load(f)
        
        # Diseases
        sql.append("\n-- Table: diseases")
        sql.append("CREATE TABLE IF NOT EXISTS diseases (name TEXT PRIMARY KEY, description TEXT, symptoms TEXT, diet_recommendation TEXT);")
        
        if "diseases" in diet:
            for name, data in diet["diseases"].items():
                cols = ["name", "description", "symptoms", "diet_recommendation"]
                vals = [
                    escape_sql(name),
                    escape_sql(data.get("description")),
                    escape_sql(json.dumps(data.get("symptoms", []))),
                    escape_sql(json.dumps(data.get("diet_recommendation", {})))
                ]
                sql.append(f"INSERT OR REPLACE INTO diseases ({', '.join(cols)}) VALUES ({', '.join(vals)});")

    sql.append("COMMIT;")
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write("\n".join(sql))
    
    print(f"Successfully generated SQL dump at: {OUTPUT_FILE}")

if __name__ == "__main__":
    generate_sql()
