"""
Base API Service with caching, retry logic, and error handling
"""
import time
import requests
from typing import Dict, Any, Optional
from functools import wraps
from backend.config import APIConfig

class BaseAPIService:
    """Base class for all API services with common functionality"""
    
    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.session = requests.Session()
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._request_times: list[float] = []
        
    def _check_rate_limit(self):
        """Ensure we don't exceed rate limits"""
        now = time.time()
        # Remove requests older than 1 minute
        self._request_times = [t for t in self._request_times if now - t < 60]
        
        if len(self._request_times) >= APIConfig.MAX_REQUESTS_PER_MINUTE:
            sleep_time = 60 - (now - self._request_times[0])
            if sleep_time > 0:
                time.sleep(sleep_time)
                self._request_times = []
        
        self._request_times.append(now)
    
    def _get_from_cache(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        if not APIConfig.CACHE_ENABLED:
            return None
            
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < APIConfig.CACHE_TTL:
                return value
            else:
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        """Set value in cache"""
        if APIConfig.CACHE_ENABLED:
            self._cache[key] = (value, time.time())
    
    def _make_request(self, endpoint: str, method: str = "GET", 
                     params: Optional[Dict] = None, 
                     data: Optional[Dict] = None) -> Any:
        """Make HTTP request with retry logic and FALLBACK to local data"""
        
        # Check Mock Mode
        if APIConfig.MOCK_MODE:
            return self._get_mock_response(endpoint, params)

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Check cache for GET requests
        if method == "GET":
            cache_key = f"{url}:{str(params)}"
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached
        
        # Try Live Request
        try:
            # Rate limiting
            self._check_rate_limit()
            
            # Add API key if available
            headers = {}
            if self.api_key:
                headers['Authorization'] = f'Bearer {self.api_key}'
            
            # Retry logic
            for attempt in range(APIConfig.MAX_RETRIES):
                try:
                    response = self.session.request(
                        method=method,
                        url=url,
                        params=params,
                        json=data,
                        headers=headers,
                        timeout=10 # Reduced timeout for faster fallback
                    )
                    response.raise_for_status()
                    result = response.json()
                    
                    # Cache successful GET requests
                    if method == "GET":
                        self._set_cache(cache_key, result)
                    
                    return result
                    
                except requests.exceptions.RequestException as e:
                    if attempt == APIConfig.MAX_RETRIES - 1:
                        raise e
                    
                    # Exponential backoff
                    sleep_time = APIConfig.RETRY_BACKOFF_FACTOR * (2 ** attempt)
                    time.sleep(sleep_time)

        except Exception as e:
            # FAILURE - Activate Fallback
            print(f"⚠️  API CONNECTION FAILED for {url}")
            print(f"⚠️  Error: {e}")
            print(f"🔄 REVERTING TO LOCAL DEMO DATABASE...")
            return self._get_mock_response(endpoint, params)
        
        return None

    def _get_mock_response(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        """
        Generate mock response from local JSON files
        """
        import json
        
        # Determine which DB to load based on the service class or endpoint
        # This is a heuristic based on the URL structure or endpoint name
        
        data = []
        try:
            if "recipe" in self.base_url or "recipes" in endpoint:
                with open(APIConfig.MOCK_RECIPES_FILE, 'r') as f:
                    data = json.load(f)
                    
                # Handle specific recipe endpoints
                if endpoint == "recipesInfo" or endpoint == "nutritionInfo" or endpoint == "micronutritionInfo":
                    recipe_id = params.get("id")
                    for r in data:
                        if str(r["id"]) == str(recipe_id):
                            if endpoint == "recipesInfo": return r
                            if endpoint == "nutritionInfo": return r.get("nutrition", {})
                            if endpoint == "micronutritionInfo": return r.get("micronutrients", {})
                    return {}
                
                if endpoint.startswith("instructions/"):
                    recipe_id = endpoint.split("/")[-1]
                    for r in data:
                        if str(r["id"]) == str(recipe_id):
                            return {"instructions": r.get("instructions", [])}
                    return {"instructions": []}

                # --- Recipe Search & Filtering ---
                filtered = data
                
                # handle recipes_cuisine/cuisine/{cuisine}
                if "recipes_cuisine/cuisine/" in endpoint:
                    cuisine_filter = endpoint.split("/")[-1].lower()
                    filtered = [r for r in filtered if cuisine_filter in [c.lower() for c in r.get("cuisines", [])]]

                # handle recipes-method/{method}
                elif "recipes-method/" in endpoint:
                    method_filter = endpoint.split("/")[-1].lower()
                    # Mock check: search instructions for method name
                    filtered = [r for r in filtered if any(method_filter in step.lower() for step in r.get("instructions", []))]

                # handle recipe-diet (params: diet)
                elif "recipe-diet" in endpoint:
                    if params and "diet" in params:
                        diet_filter = params["diet"].lower()
                        filtered = [r for r in filtered if diet_filter in [d.lower() for d in r.get("diets", [])]]
                
                # handle generic filters via params
                if params:
                    if "query" in params or "title" in params: # recipeByTitle matches here
                        q = params.get("query", params.get("title", "")).lower()
                        filtered = [r for r in filtered if q in r["title"].lower()]
                    
                    if "min" in params and "max" in params:
                        # Calories, Protein, Carbs, Weight ranges
                        # Heuristic: Identify what we are filtering by endpoint name
                        try:
                            val_min = float(params["min"])
                            val_max = float(params["max"])
                            
                            if "calories" in endpoint:
                                filtered = [r for r in filtered if val_min <= r["nutrition"]["calories"] <= val_max]
                            elif "protein" in endpoint:
                                filtered = [r for r in filtered if val_min <= int(r["nutrition"]["protein"].replace('g','')) <= val_max]
                            elif "carbs" in endpoint:
                                filtered = [r for r in filtered if val_min <= int(r["nutrition"]["carbohydrates"].replace('g','')) <= val_max]
                        except: pass

                    if "day" in params: # recipesDay
                        # Return random subset for variety
                        pass 

                    if "utensils" in params: # bydetails/utensils
                        pass
                
                # Default list return with limit
                limit = int(params.get("limit", 50)) if params else 50
                return filtered[:limit]

            elif "flavor" in self.base_url or "flavor" in endpoint.lower():
                with open(APIConfig.MOCK_FLAVOR_DB_FILE, 'r') as f:
                    data = json.load(f)
                
                # Direct Ingredient Lookups
                ingredient = params.get("ingredient")
                if ingredient and ingredient in data:
                     item = data[ingredient]
                     mol = item.get("molecular_properties", {})
                     
                     if "flavorProfile" in endpoint: return item
                     if "functionalGroups" in endpoint: return {"functional_groups": item.get("functional_groups", [])}
                     if "aromaThreshold" in endpoint: return {"threshold": item.get("aroma_threshold", 1.0)}
                     if "taste-threshold" in endpoint: return {"threshold": item.get("taste_threshold", 1.0)}
                     if "by-description" in endpoint: return item.get("molecular_properties", {})
                     
                     # Molecular properties specific endpoints
                     if "aromaticRings" in endpoint: return {"aromatic_rings": 2} # Mock
                     if "monoisotopicMass" in endpoint: return {"mass": mol.get("weight", 0.0)}
                     if "alogp" in endpoint: return {"alogp": mol.get("alogp", 0.0)}
                     if "topologicalPolarSurfaceArea" in endpoint: return {"psa": 45.0} # Mock
                     if "hbd-count" in endpoint: return {"hbd_count": mol.get("hbd_count", 0)}
                     if "hba-count" in endpoint: return {"hba_count": mol.get("hba_count", 0)}
                     
                     # Safety & Occurrence
                     if "by-fema" in endpoint: return {"approved": item["safety_approvals"]["fema"]}
                     if "by-jecfa" in endpoint: return {"approved": item["safety_approvals"]["jecfa"]}
                     if "by-efsa" in endpoint: return {"approved": item["safety_approvals"]["efsa"]}
                     if "by-naturalOccurrence" in endpoint: return {"natural": item["natural_occurrence"]}

                # Search & Filtering
                if "by-commonName" in endpoint:
                    name = params.get("name", "").lower()
                    for k, v in data.items():
                        if name in k.lower(): return v
                    return {}
                
                if "by-name-and-category" in endpoint:
                    cat = params.get("category", "")
                    return [v for v in data.values() if v.get("category") == cat]
                
                if "filter-by-weight-range" in endpoint:
                     min_w = float(params.get("min", 0))
                     max_w = float(params.get("max", 1000))
                     return [v for v in data.values() if min_w <= v["molecular_properties"].get("weight", 0) <= max_w]

                if endpoint == "synthesis":
                    # Mock synthesis
                    return {"pairing_score": 0.85, "molecules": ["mock_mol_1", "mock_mol_2"]}
                    
                return {}

            elif "dietrx" in self.base_url:
                with open(APIConfig.MOCK_DIET_RX_FILE, 'r') as f:
                    db = json.load(f)
                
                if endpoint.startswith("disease/"):
                    disease = endpoint.split("/")[-1]
                    return db["diseases"].get(disease, {})
                
                if endpoint.startswith("food-interactions/"):
                    food = endpoint.split("/")[-1]
                    return db["interactions"].get(food, [])
                
                return {}

            elif "sustainable" in self.base_url:
                with open(APIConfig.MOCK_SUSTAINABLE_DB_FILE, 'r') as f:
                    data = json.load(f)
                
                if endpoint == "search":
                    q = params.get("q", "").lower()
                    return [{"name": k, **v} for k, v in data.items() if q in k.lower()]

                if endpoint == "ingredient-cf":
                    ing = params.get("ingredient")
                    item = data.get(ing, {"carbon_footprint_kg": 0.5})
                    # Service expects "carbon_footprint"
                    return {"carbon_footprint": item.get("carbon_footprint_kg", 0.5)}
                
                if endpoint.endswith("/carbon-footprint-name"):
                    # {food_name}/carbon-footprint-name
                    food_name = endpoint.split("/")[0]
                    item = data.get(food_name, {"carbon_footprint_kg": 0.5})
                    return {"carbon_footprint": item.get("carbon_footprint_kg", 0.5)}

                if endpoint == "carbon-footprint-sum":
                    ings = params.get("ingredients", "").split(",")
                    # Sum up carbon_footprint_kg
                    total = sum([data.get(i.strip(), {}).get("carbon_footprint_kg", 0.5) for i in ings])
                    return {"total_carbon": total}
                
                if endpoint.startswith("recipe/"):
                    # Mock recipe footprint based on average
                    return {"carbon_footprint": 2.5, "rating": "Good"}
                
                return []

        except Exception as e:
            print(f"Mock Data Error for {endpoint}: {e}")
            return {}
        
        return {}
