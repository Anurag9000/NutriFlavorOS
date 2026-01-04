from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn

from backend.models import UserProfile, PlanResponse

from backend.engines.plan_generator import PlanGenerator

app = FastAPI(title="NutriFlavorOS API", version="0.1.0")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for prototype
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Generator (loads DB)
generator = PlanGenerator()

@app.get("/")
def read_root():
    return {"message": "Welcome to NutriFlavorOS API"}

@app.post("/generate_plan", response_model=PlanResponse)
def generate_meal_plan(user: UserProfile):
    """
    Generate a personalized meal plan based on user profile.
    This uses the Health, Taste, and Variety engines.
    """
    try:
        plan = generator.create_plan(user, days=3)
        return plan
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
