from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn

from backend.models import UserProfile, PlanResponse

from backend.engines.plan_generator import PlanGenerator

# Import Routers
from backend.api import (
    user_routes,
    meal_routes,
    analytics_routes,
    recipe_routes,
    vision_routes,
    sustainability_routes,
    online_learning_routes
)

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

# Mount Routers
app.include_router(user_routes.router)
app.include_router(meal_routes.router)
app.include_router(analytics_routes.router)
app.include_router(recipe_routes.router)
app.include_router(vision_routes.router)
app.include_router(sustainability_routes.router)
app.include_router(online_learning_routes.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
