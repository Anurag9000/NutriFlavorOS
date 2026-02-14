"""
Configuration for external API services
"""
import os
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(env_path)

class APIConfig:
    """Configuration for all external APIs"""
    
    # RecipeDB Configuration
    RECIPEDB_BASE_URL: str = os.getenv("RECIPEDB_BASE_URL", "http://cosylab.iiitd.edu.in:6969")
    RECIPEDB_API_KEY: Optional[str] = os.getenv("RECIPEDB_API_KEY")
    
    # FlavorDB Configuration
    FLAVORDB_BASE_URL: str = os.getenv("FLAVORDB_BASE_URL", "http://cosylab.iiitd.edu.in:6969/flavordb")
    FLAVORDB_API_KEY: Optional[str] = os.getenv("FLAVORDB_API_KEY")
    
    # SustainableFoodDB Configuration
    SUSTAINABLEFOODDB_BASE_URL: str = os.getenv("SUSTAINABLEFOODDB_BASE_URL", "http://cosylab.iiitd.edu.in:6969/sustainablefooddb")
    SUSTAINABLEFOODDB_API_KEY: Optional[str] = os.getenv("SUSTAINABLEFOODDB_API_KEY")
    
    # DietRxDB Configuration
    DIETRXDB_BASE_URL: str = os.getenv("DIETRXDB_BASE_URL", "http://cosylab.iiitd.edu.in:6969/dietrxdb")
    DIETRXDB_API_KEY: Optional[str] = os.getenv("DIETRXDB_API_KEY")
    
    # Cache Configuration
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour default
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 0.5

    # Mock Mode Configuration
    # Defaults to True if API keys are not set, or can be forced via env var
    MOCK_MODE: bool = os.getenv("MOCK_MODE", "false").lower() == "true"
    
    # Mock Data Paths
    # config.py is in backend/, so we want backend/data
    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "data")
    MOCK_RECIPES_FILE: str = os.path.join(DATA_DIR, "recipes.json")
    MOCK_FLAVOR_DB_FILE: str = os.path.join(DATA_DIR, "flavor_db.json")
    MOCK_DIET_RX_FILE: str = os.path.join(DATA_DIR, "diet_rx_db.json")
    MOCK_SUSTAINABLE_DB_FILE: str = os.path.join(DATA_DIR, "sustainable_db.json")
