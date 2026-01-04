from backend.models import UserProfile, NutrientTarget, Gender, Goal

class HealthEngine:
    @staticmethod
    def calculate_bmr(user: UserProfile) -> float:
        # Mifflin-St Jeor Equation
        if user.gender == Gender.MALE:
            bmr = (10 * user.weight_kg) + (6.25 * user.height_cm) - (5 * user.age) + 5
        else:
            bmr = (10 * user.weight_kg) + (6.25 * user.height_cm) - (5 * user.age) - 161
        return bmr

    @staticmethod
    def calculate_targets(user: UserProfile) -> NutrientTarget:
        bmr = HealthEngine.calculate_bmr(user)
        tdee = bmr * user.activity_level
        
        # Adjust for goal
        target_calories = tdee
        if user.goal == Goal.WEIGHT_LOSS:
            target_calories -= 500
        elif user.goal == Goal.MUSCLE_GAIN:
            target_calories += 400 # Moderate surplus
            
        target_calories = max(1200, target_calories) # Safety floor
        
        # Macro Split (Default Balanced: 30% Protein, 35% Carbs, 35% Fat)
        # Protein: 4 cal/g, Carbs: 4 cal/g, Fat: 9 cal/g
        
        if user.goal == Goal.MUSCLE_GAIN:
            p_ratio, c_ratio, f_ratio = 0.35, 0.40, 0.25
        elif user.goal == Goal.WEIGHT_LOSS:
            p_ratio, c_ratio, f_ratio = 0.40, 0.30, 0.30
        else:
            p_ratio, c_ratio, f_ratio = 0.30, 0.35, 0.35
            
        protein_g = (target_calories * p_ratio) / 4
        carbs_g = (target_calories * c_ratio) / 4
        fat_g = (target_calories * f_ratio) / 9
        
        return NutrientTarget(
            calories=int(target_calories),
            protein_g=int(protein_g),
            carbs_g=int(carbs_g),
            fat_g=int(fat_g),
            micro_nutrients={"Iron": 18, "Calcium": 1000, "Vitamin C": 90} # Simplified defaults
        )

    @staticmethod
    def score_recipe(recipe_macros: dict, target_macros: NutrientTarget) -> float:
        """
        Score how well a single recipe fits into a daily portion of the target.
        Assuming 3 meals/day, a meal should roughly provide 33% of daily needs.
        """
        target_cal_per_meal = target_macros.calories / 3.0
        
        # Simple percentage deviation score
        diff = abs(recipe_macros.get("calories", 0) - target_cal_per_meal)
        percentage_diff = diff / target_cal_per_meal
        
        # Score: 1.0 is perfect match, drops as diff increases
        score = max(0, 1.0 - percentage_diff)
        return score
