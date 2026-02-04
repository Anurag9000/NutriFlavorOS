"""
FlavorDB API Service - 24,000+ ingredients with molecular flavor data
"""
from typing import List, Dict, Any, Optional
from backend.services.base_service import BaseAPIService
from backend.config import APIConfig

class FlavorDBService(BaseAPIService):
    """Service for interacting with FlavorDB API - Molecular flavor analysis"""
    
    def __init__(self):
        super().__init__(
            base_url=APIConfig.FLAVORDB_BASE_URL,
            api_key=APIConfig.FLAVORDB_API_KEY
        )
    
    def get_flavor_profile(self, ingredient: str) -> Dict[str, Any]:
        """Get complete flavor profile vector for an ingredient"""
        return self._make_request("by-flavorProfile", params={"ingredient": ingredient})
    
    def get_functional_groups(self, ingredient: str) -> List[str]:
        """Get chemical functional groups present in ingredient"""
        result = self._make_request("by-functionalGroups", params={"ingredient": ingredient})
        return result.get("functional_groups", [])
    
    def get_aroma_threshold(self, ingredient: str) -> float:
        """Get aroma detection threshold (lower = stronger aroma)"""
        result = self._make_request("by-aromaThresholdValues", params={"ingredient": ingredient})
        return result.get("threshold", 1.0)
    
    def get_taste_threshold(self, ingredient: str) -> float:
        """Get taste perception threshold"""
        result = self._make_request("taste-threshold", params={"ingredient": ingredient})
        return result.get("threshold", 1.0)
    
    def synthesize_flavor_pairing(self, ing1: str, ing2: str) -> Dict[str, Any]:
        """Analyze molecular compatibility between two ingredients"""
        return self._make_request("synthesis", params={"ing1": ing1, "ing2": ing2})
    
    def search_by_common_name(self, name: str) -> Dict[str, Any]:
        """Search ingredient by common name"""
        return self._make_request("by-commonName", params={"name": name})
    
    def search_by_category(self, category: str) -> List[Dict]:
        """Get all ingredients in a category"""
        return self._make_request("by-name-and-category", params={"category": category})
    
    def get_molecular_properties(self, ingredient: str) -> Dict[str, Any]:
        """Get detailed molecular properties"""
        return self._make_request("by-description", params={"ingredient": ingredient})
    
    def get_aromatic_rings(self, ingredient: str) -> int:
        """Get number of aromatic rings (affects flavor intensity)"""
        result = self._make_request("by-aromaticRings", params={"ingredient": ingredient})
        return result.get("aromatic_rings", 0)
    
    def get_molecular_weight(self, ingredient: str) -> float:
        """Get molecular weight"""
        result = self._make_request("by-monoisotopicMass", params={"ingredient": ingredient})
        return result.get("mass", 0.0)
    
    def get_lipophilicity(self, ingredient: str) -> float:
        """Get AlogP (lipophilicity index) - affects fat solubility"""
        result = self._make_request("by-alogp", params={"ingredient": ingredient})
        return result.get("alogp", 0.0)
    
    def filter_by_weight_range(self, min_weight: float, max_weight: float) -> List[Dict]:
        """Filter ingredients by molecular weight range"""
        return self._make_request("filter-by-weight-range", 
                                 params={"min": min_weight, "max": max_weight})
    
    def get_polar_surface_area(self, ingredient: str) -> float:
        """Get topological polar surface area (affects solubility)"""
        result = self._make_request("by-topologicalPolarSurfaceArea", 
                                   params={"ingredient": ingredient})
        return result.get("psa", 0.0)
    
    def get_hbond_donors(self, ingredient: str) -> int:
        """Get hydrogen bond donor count"""
        result = self._make_request("filter-by-hbd-count", params={"ingredient": ingredient})
        return result.get("hbd_count", 0)
    
    def get_hbond_acceptors(self, ingredient: str) -> int:
        """Get hydrogen bond acceptor count"""
        result = self._make_request("filter-by-hba-count", params={"ingredient": ingredient})
        return result.get("hba_count", 0)
    
    def check_safety_approval(self, ingredient: str) -> Dict[str, bool]:
        """Check regulatory approvals (FEMA, JECFA, EFSA, etc.)"""
        approvals = {}
        approvals["fema"] = self._make_request("by-fema", params={"ingredient": ingredient}).get("approved", False)
        approvals["jecfa"] = self._make_request("by-jecfa", params={"ingredient": ingredient}).get("approved", False)
        approvals["efsa"] = self._make_request("by-efsa", params={"ingredient": ingredient}).get("approved", False)
        return approvals
    
    def get_natural_occurrence(self, ingredient: str) -> bool:
        """Check if ingredient occurs naturally"""
        result = self._make_request("by-naturalOccurrence", params={"ingredient": ingredient})
        return result.get("natural", False)
    
    def calculate_flavor_similarity(self, ing1: str, ing2: str) -> float:
        """
        Calculate molecular similarity between two ingredients
        Returns: similarity score 0.0-1.0
        """
        profile1 = self.get_flavor_profile(ing1)
        profile2 = self.get_flavor_profile(ing2)
        
        if not profile1 or not profile2:
            return 0.0
        
        # Cosine similarity on flavor vectors
        vector1 = profile1.get("flavor_vector", {})
        vector2 = profile2.get("flavor_vector", {})
        
        if not vector1 or not vector2:
            return 0.0
        
        # Calculate dot product and magnitudes
        dot_product = sum(vector1.get(k, 0) * vector2.get(k, 0) for k in set(vector1) | set(vector2))
        mag1 = sum(v**2 for v in vector1.values()) ** 0.5
        mag2 = sum(v**2 for v in vector2.values()) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
