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
        """Make HTTP request with retry logic"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Check cache for GET requests
        if method == "GET":
            cache_key = f"{url}:{str(params)}"
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                return cached
        
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
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                
                # Cache successful GET requests
                if method == "GET":
                    self._set_cache(cache_key, result)
                
                return result
                
            except requests.exceptions.RequestException as e:
                if attempt == APIConfig.MAX_RETRIES - 1:
                    raise Exception(f"API request failed after {APIConfig.MAX_RETRIES} attempts: {str(e)}")
                
                # Exponential backoff
                sleep_time = APIConfig.RETRY_BACKOFF_FACTOR * (2 ** attempt)
                time.sleep(sleep_time)
        
        return None
