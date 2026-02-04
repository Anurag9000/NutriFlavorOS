"""
Configuration for external API services
"""
import os
from typing import Optional

class APIConfig:
    """Configuration for all external APIs"""
    
    # RecipeDB Configuration
    RECIPEDB_BASE_URL: str = os.getenv("RECIPEDB_BASE_URL", "https://cosylab.iiitd.edu.in/recipedb/")
    RECIPEDB_API_KEY: Optional[str] = os.getenv("RECIPEDB_API_KEY")
    
    # FlavorDB Configuration
    FLAVORDB_BASE_URL: str = os.getenv("FLAVORDB_BASE_URL", "https://cosylab.iiitd.edu.in/flavordb/")
    FLAVORDB_API_KEY: Optional[str] = os.getenv("FLAVORDB_API_KEY")
    
    # SustainableFoodDB Configuration
    SUSTAINABLEFOODDB_BASE_URL: str = os.getenv("SUSTAINABLEFOODDB_BASE_URL", "https://cosylab.iiitd.edu.in/sustainablefooddb/")
    SUSTAINABLEFOODDB_API_KEY: Optional[str] = os.getenv("SUSTAINABLEFOODDB_API_KEY")
    
    # DietRxDB Configuration
    DIETRXDB_BASE_URL: str = os.getenv("DIETRXDB_BASE_URL", "https://cosylab.iiitd.edu.in/dietrxdb/")
    DIETRXDB_API_KEY: Optional[str] = os.getenv("DIETRXDB_API_KEY")
    
    # Cache Configuration
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour default
    CACHE_ENABLED: bool = os.getenv("CACHE_ENABLED", "true").lower() == "true"
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
    
    # Retry Configuration
    MAX_RETRIES: int = 3
    RETRY_BACKOFF_FACTOR: float = 0.5
