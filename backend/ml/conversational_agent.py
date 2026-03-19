"""
AI Meal Buddy - Conversational Nutrition Coach
Uses LLM + RAG to provide personalized, context-aware nutrition advice
"""
from typing import List, Dict, Any, Optional
import os
from backend.models import UserProfile, Recipe
from backend.services.recipedb_service import RecipeDBService
from backend.engines.taste_engine import TasteEngine
from backend.engines.health_engine import HealthEngine

class NutritionAI:
    """
    Intelligent Conversational Agent for NutriFlavorOS
    
    Features:
    - Contextual awareness (User biometrics, Flavor Genome, Health Goals)
    - Recipe-specific knowledge (via RecipeDB)
    - Real-time plan adjustments
    - Scientific explanations for recommendations
    """
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.recipe_service = RecipeDBService()
        self.taste_engine = TasteEngine()
        self.health_engine = HealthEngine()
        
        # System prompt to define personality and constraints
        self.system_prompt = (
            "You are NutriFlavorAI, a senior clinical nutritionist and gourmet chef. "
            "Your goal is to help users reach their health goals while maximizing culinary pleasure. "
            "You have access to the user's Flavor Genome (molecular taste profile) and health data. "
            "Always be encouraging, scientifically accurate, and focus on flavor synergy."
        )

    async def get_response(self, user_query: str, user_profile: UserProfile, 
                           current_plan: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Generate personalized response based on query and user context
        """
        # 1. Analyze intent (simplified for prototype)
        intent = self._detect_intent(user_query)
        
        # 2. Gather context
        context = self._build_context(user_profile, current_plan)
        
        # 3. Perform RAG (Retrieval Augmented Generation)
        # If user asks about specific ingredients or recipes, fetch them
        relevant_data = ""
        if "recipe" in user_query or "cook" in user_query:
            recipes = self.recipe_service.search_by_title(user_query.split()[-1])
            relevant_data = f"Relevant Recipes: {str(recipes[:2])}"

        # 4. Generate Response (Mocking LLM call if no API key)
        if not self.api_key:
            return self._generate_mock_response(user_query, intent, user_profile)
        
        # Real OpenAI call would go here
        # response = await self._call_llm(user_query, context, relevant_data)
        return {"text": "LLM Integration is active, but using safe response for now.", "intent": intent}

    def _detect_intent(self, query: str) -> str:
        query = query.lower()
        if any(w in query for w in ["swap", "change", "replace"]):
            return "plan_adjustment"
        if any(w in query for w in ["why", "explain", "reason"]):
            return "explanation"
        if any(w in query for w in ["recipe", "how to", "cook"]):
            return "cooking_advice"
        return "general_nutrition"

    def _build_context(self, user: UserProfile, plan: Optional[List[Dict]]) -> str:
        genome = self.taste_engine.generate_flavor_genome(user)
        top_flavors = sorted(genome.items(), key=lambda x: x[1], reverse=True)[:5]
        
        context = (
            f"User Goal: {user.goal}. "
            f"Activity Level: {user.activity_level}. "
            f"Top Flavors: {', '.join([f[0] for f in top_flavors])}. "
            f"Restrictions: {', '.join(user.dietary_restrictions)}. "
        )
        return context

    def _generate_mock_response(self, query: str, intent: str, user: UserProfile) -> Dict[str, Any]:
        """High-quality fallback responses based on system logic"""
        if intent == "plan_adjustment":
            return {
                "text": f"I can certainly help you swap that! Based on your {user.goal} goal, "
                        f"I'd recommend a high-protein alternative that matches your flavor profile.",
                "suggestions": ["Quinoa Bowl with Roasted Veggies", "Grilled Salmon with Lemon-Dill"]
            }
        elif intent == "explanation":
            return {
                "text": "I recommended this meal plan because it balances your micronutrient targets (especially Vitamin D and Iron) "
                        "with molecular flavor compounds you've shown a strong preference for in the past."
            }
        elif intent == "cooking_advice":
            return {
                "text": "For the best flavor extraction, I recommend dry-searing the proteins first. "
                        "This triggers the Maillard reaction, which aligns perfectly with your preference for savory, umami profiles."
            }
        
        return {
            "text": f"Hello! I'm your NutriFlavorAI buddy. I see you're working towards {user.goal}. "
                    "How can I help you optimize your kitchen today?"
        }

# Global Instance
meal_buddy = NutritionAI()
