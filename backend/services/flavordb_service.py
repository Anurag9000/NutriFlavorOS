import json
import os
from typing import List, Dict, Any, Optional
from backend.services.base_service import BaseAPIService
from backend.config import APIConfig

class FlavorDBService(BaseAPIService):
    """Service for interacting with FlavorDB - prioritizing Local JSON data"""
    
    def __init__(self):
        super().__init__(
            base_url=APIConfig.FLAVORDB_BASE_URL,
            api_key=APIConfig.FLAVORDB_API_KEY
        )
        self.local_db = {} # Unused, relying on BaseAPIService fallback loading


    # _get_local_data Removed - BaseAPIService handles fallback


    def get_flavor_profile(self, ingredient: str) -> Dict[str, Any]:
        """Get complete flavor profile vector"""
        # API First

        mol = self.get_molecule_details(ingredient)
        return mol.get("flavor_profile") if mol else {}
    
    def get_functional_groups(self, ingredient: str) -> List[str]:
        """Get chemical functional groups"""

        mol = self.get_molecule_details(ingredient)
        return mol.get("functional_groups", []) if mol else []
    
    def get_aroma_threshold(self, ingredient: str) -> float:
        """Get aroma detection threshold"""

        mol = self.get_molecule_details(ingredient)
        return mol.get("threshold", 1.0) if mol else 1.0
    
    def get_taste_threshold(self, ingredient: str) -> float:
        """Get taste perception threshold"""

        mol = self.get_molecule_details(ingredient)
        return mol.get("taste_threshold", 1.0) if mol else 1.0
    
    def synthesize_flavor_pairing(self, ing1: str, ing2: str) -> Dict[str, Any]:
        """Analyze molecular compatibility/pairing"""

        return self._make_request("food/by-alias", params={"food_pair": ing1})
    
    def search_entities_by_readable_name(self, name: str) -> Dict[str, Any]:
        """Search entity"""
        return self._make_request("entities/by-entity-alias-readable", params={"entity_alias_readable": name})

    def get_molecule_details(self, common_name: str) -> Dict[str, Any]:
        """Get molecule details"""
        res = self._make_request("molecules_data/by-commonName", params={"common_name": common_name})
        if isinstance(res, dict) and "content" in res and isinstance(res["content"], list) and res["content"]:
             return res["content"][0]
        return {}
    
    def search_by_common_name(self, name: str) -> Dict[str, Any]:
        return self.search_entities_by_readable_name(name)
    
    def search_by_category(self, category: str) -> List[Dict]:
        return self._make_request("entities/by-name-and-category", params={"category": category, "name": ""})
    
    def get_molecular_properties(self, ingredient: str) -> Dict[str, Any]:
        return self.get_molecule_details(ingredient)
    
    def get_aromatic_rings(self, ingredient: str) -> int:
        mol = self.get_molecule_details(ingredient)
        return mol.get("aromatic_rings", 0) if mol else 0
    
    def get_molecular_weight(self, ingredient: str) -> float:
        mol = self.get_molecule_details(ingredient)
        return mol.get("molecular_weight", 0.0) if mol else 0.0
    
    def get_lipophilicity(self, ingredient: str) -> float:
        mol = self.get_molecule_details(ingredient)
        return mol.get("xlogp", 0.0) if mol else 0.0
    
    def filter_by_weight_range(self, min_weight: float, max_weight: float) -> List[Dict]:
        return self._make_request("molecules_data/filter-by-weight-range", 
                                 params={"min": min_weight, "max": max_weight})
    
    def get_polar_surface_area(self, ingredient: str) -> float:
        mol = self.get_molecule_details(ingredient)
        return mol.get("topological_polor_surfacearea", 0.0) if mol else 0.0
    
    def get_hbond_donors(self, ingredient: str) -> int:
        mol = self.get_molecule_details(ingredient)
        return mol.get("hbd_count", 0) if mol else 0
    
    def get_hbond_acceptors(self, ingredient: str) -> int:
        mol = self.get_molecule_details(ingredient)
        return mol.get("hba_count", 0) if mol else 0
    
    def check_safety_approval(self, ingredient: str) -> Dict[str, bool]:
        mol = self.get_molecule_details(ingredient)
        return {
            "fema": bool(mol.get("fema_number")),
            "natural": mol.get("natural", False)
        }
    
    def get_natural_occurrence(self, ingredient: str) -> bool:
        mol = self.get_molecule_details(ingredient)
        return mol.get("natural", False) if mol else False
    
    def calculate_flavor_similarity(self, ing1: str, ing2: str) -> float:
        """
        Calculate molecular similarity between two ingredients
        Returns: similarity score 0.0-1.0
        """
        try:
            profile1 = self.get_flavor_profile(ing1)
            profile2 = self.get_flavor_profile(ing2)
            
            if not profile1 or not profile2:
                return 0.0
            
            # Use flavor vectors if available
            v1 = profile1.get("flavor_vector", {})
            v2 = profile2.get("flavor_vector", {})
            
            if v1 and v2:
                # Simple Jaccard/Cosine sim implementation for dictionaries
                keys1 = set(v1.keys())
                keys2 = set(v2.keys())
                intersection = keys1.intersection(keys2)
                union = keys1.union(keys2)
                if not union: return 0.0
                return len(intersection) / len(union)

            return 0.5 # Default middle ground if no fine-grained vectors
        except:
            return 0.0
