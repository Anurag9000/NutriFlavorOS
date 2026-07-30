"""Configuration for optional external data services.

External services are opt-in. Missing credentials or network failures must not
silently turn into fabricated data that is indistinguishable from a live result.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv


load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=False)


def _bool_env(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class APIConfig:
    RECIPEDB_BASE_URL: str = os.getenv("RECIPEDB_BASE_URL", "https://cosylab.iiitd.edu.in")
    RECIPEDB_API_KEY: Optional[str] = os.getenv("RECIPEDB_API_KEY")

    FLAVORDB_BASE_URL: str = os.getenv("FLAVORDB_BASE_URL", "https://cosylab.iiitd.edu.in/flavordb")
    FLAVORDB_API_KEY: Optional[str] = os.getenv("FLAVORDB_API_KEY")

    SUSTAINABLEFOODDB_BASE_URL: str = os.getenv(
        "SUSTAINABLEFOODDB_BASE_URL", "https://cosylab.iiitd.edu.in/sustainablefooddb"
    )
    SUSTAINABLEFOODDB_API_KEY: Optional[str] = os.getenv("SUSTAINABLEFOODDB_API_KEY")

    DIETRXDB_BASE_URL: str = os.getenv("DIETRXDB_BASE_URL", "https://cosylab.iiitd.edu.in/dietrxdb")
    DIETRXDB_API_KEY: Optional[str] = os.getenv("DIETRXDB_API_KEY")

    CACHE_TTL: int = max(0, int(os.getenv("CACHE_TTL", "300")))
    CACHE_ENABLED: bool = _bool_env("CACHE_ENABLED", True)
    CACHE_MAX_ENTRIES: int = max(1, int(os.getenv("CACHE_MAX_ENTRIES", "512")))

    MAX_REQUESTS_PER_MINUTE: int = max(1, int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60")))
    MAX_RETRIES: int = max(1, int(os.getenv("MAX_RETRIES", "3")))
    RETRY_BACKOFF_FACTOR: float = max(0.0, float(os.getenv("RETRY_BACKOFF_FACTOR", "0.5")))
    REQUEST_TIMEOUT_SECONDS: float = max(0.1, float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")))

    MOCK_MODE: bool = _bool_env("MOCK_MODE", False)

    DATA_DIR: str = os.path.join(os.path.dirname(__file__), "data")
    MOCK_RECIPES_FILE: str = os.path.join(DATA_DIR, "recipes.json")
    MOCK_FLAVOR_DB_FILE: str = os.path.join(DATA_DIR, "flavor_db.json")
    MOCK_DIET_RX_FILE: str = os.path.join(DATA_DIR, "diet_rx_db.json")
    MOCK_SUSTAINABLE_DB_FILE: str = os.path.join(DATA_DIR, "sustainable_db.json")
