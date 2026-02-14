from fastapi import APIRouter, HTTPException, Query
from typing import List, Optional, Dict
from backend.models import Recipe
from backend.services.recipedb_service import RecipeDBService

router = APIRouter(prefix="/api/v1/recipes", tags=["recipes"])

# Initialize Service
recipe_service = RecipeDBService()

@router.get("/search", response_model=List[Dict])
async def search_recipes(
    q: Optional[str] = None, 
    tags: Optional[str] = None,
    limit: int = 20
):
    """
    Search recipes using RecipeDB service
    """
    try:
        if not q and not tags:
            # Default to some popular recipes if no query
            return recipe_service.search_by_calories(300, 600, limit=limit)
            
        if q:
            # Search by title
            results = recipe_service.search_by_title(q)
            # Filter by tags if provided (client-side filtering as DB might not support complex AND)
            if tags:
                tag_list = [t.lower() for t in tags.split(",")]
                # This depends on response structure, assuming 'tags' or 'category' field exists
                # For now, we return direct results to ensure data flow
            return results[:limit]
            
        if tags:
            # If only tags provided, maybe search by category or key ingredient
            # Mapping common tags to service methods
            tag_list = tags.lower().split(",")
            if "low-carb" in tag_list:
                return recipe_service.search_by_carbs(0, 20, limit=limit)
            elif "high-protein" in tag_list:
                return recipe_service.search_by_protein(30, 100, limit=limit)
            elif "vegetarian" in tag_list:
                 return recipe_service.get_diet_specific_recipes("High Protein Vegetarian", limit=limit)
            else:
                # Fallback to general search with first tag
                return recipe_service.search_by_title(tag_list[0])
                
        return []
    except Exception as e:
        print(f"Recipe Search Error: {e}")
        # Fallback to empty list or mock if service fails (graceful degradation)
        return []

@router.get("/{recipe_id}")
async def get_recipe_details(recipe_id: str):
    """
    Get detailed recipe info including nutrition and instructions
    """
    try:
        # Fetch data in parallel conceptually (or sequential for now)
        info = recipe_service.get_recipe_info(recipe_id)
        
        if not info:
             raise HTTPException(status_code=404, detail="Recipe not found")

        nutrition = recipe_service.get_nutrition_info(recipe_id)
        micronutrition = recipe_service.get_micronutrition_info(recipe_id)
        
        # Merge nutrition and micronutrition
        full_nutrition = {**nutrition, **micronutrition}

        instructions_list = recipe_service.get_recipe_instructions(recipe_id)
        
        # Logic to pick best instructions
        final_instructions = []
        if instructions_list:
            final_instructions = instructions_list
        elif info.get("instructions"):
             final_instructions = info.get("instructions")
        
        # Merge data into a unified response format expected by frontend
        full_details = {
            **info,
            "nutrition": full_nutrition,
            "instructions": final_instructions, 
            # Ensure ID is present
            "id": recipe_id
        }
        return full_details
        
    except Exception as e:
        print(f"Error fetching recipe details: {e}")
        # Return partial info if available, or raise
        # Better to fail gracefully if we can't get anything, but 404 already handled
        raise HTTPException(status_code=500, detail=str(e))
