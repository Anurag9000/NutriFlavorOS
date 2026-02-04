"""
DietRxDB API Service - Medical nutrition and disease management
"""
from typing import List, Dict, Any, Optional
from backend.services.base_service import BaseAPIService
from backend.config import APIConfig

class DietRxDBService(BaseAPIService):
    """Service for medical nutrition and disease-specific dietary recommendations"""
    
    def __init__(self):
        super().__init__(
            base_url=APIConfig.DIETRXDB_BASE_URL,
            api_key=APIConfig.DIETRXDB_API_KEY
        )
    
    def get_disease_info(self, disease_name: str) -> Dict[str, Any]:
        """Get comprehensive information about a disease and dietary recommendations"""
        return self._make_request(f"disease/{disease_name}")
    
    def get_all_diseases(self) -> List[Dict]:
        """Get list of all diseases in database"""
        return self._make_request("all-details")
    
    def get_disease_associations(self, association_type: str) -> List[Dict]:
        """Get diseases by association type (beneficial/harmful)"""
        return self._make_request(f"all-details/{association_type}")
    
    def get_food_properties(self, food_name: str) -> Dict[str, Any]:
        """Get health properties and effects of a food"""
        return self._make_request(f"food/{food_name}")
    
    def get_food_interactions(self, food_name: str) -> List[Dict]:
        """Get drug-food interactions (CRITICAL for safety)"""
        return self._make_request(f"food-interactions/{food_name}")
    
    def get_disease_chemicals(self, food_name: str) -> List[Dict]:
        """Get disease-relevant chemical compounds in food"""
        return self._make_request(f"disease-chemicals/{food_name}")
    
    def get_chemical_details(self, food_name: str) -> Dict[str, Any]:
        """Get detailed chemical composition"""
        return self._make_request(f"chemical-details/{food_name}")
    
    def get_gene_source(self, food_name: str) -> Dict[str, Any]:
        """Get genetic food interactions (nutrigenomics)"""
        return self._make_request(f"gene-source/{food_name}")
    
    def get_publications(self, food_name: str) -> List[Dict]:
        """Get scientific research publications"""
        return self._make_request(f"publication/{food_name}")
    
    def get_disease_publications(self, disease_name: str) -> List[Dict]:
        """Get research summaries for a disease"""
        return self._make_request(f"diseases/publicationsParsed/{disease_name}")
    
    def get_food_therapeutic_actions(self, food_name: str) -> List[str]:
        """Get therapeutic actions of a food"""
        result = self._make_request(f"diseases/diseaseNames/action/{food_name}")
        return result.get("actions", [])
    
    def check_condition_compatibility(self, food_name: str, conditions: List[str]) -> Dict[str, Any]:
        """
        Check if a food is safe/beneficial for given health conditions
        Returns: compatibility score, warnings, recommendations
        """
        warnings = []
        benefits = []
        
        for condition in conditions:
            disease_info = self.get_disease_info(condition)
            
            # Check if food is beneficial or harmful
            if disease_info:
                beneficial_foods = disease_info.get("beneficial_foods", [])
                harmful_foods = disease_info.get("harmful_foods", [])
                
                if food_name.lower() in [f.lower() for f in harmful_foods]:
                    warnings.append(f"May worsen {condition}")
                elif food_name.lower() in [f.lower() for f in beneficial_foods]:
                    benefits.append(f"Beneficial for {condition}")
        
        # Check drug interactions
        interactions = self.get_food_interactions(food_name)
        if interactions:
            warnings.extend([f"Drug interaction: {i.get('drug', 'Unknown')}" for i in interactions])
        
        # Calculate compatibility score
        score = 100
        score -= len(warnings) * 30  # Each warning reduces score
        score += len(benefits) * 10   # Each benefit increases score
        score = max(0, min(100, score))
        
        return {
            "compatible": score >= 50,
            "score": score,
            "warnings": warnings,
            "benefits": benefits,
            "safe_to_consume": len(warnings) == 0
        }
