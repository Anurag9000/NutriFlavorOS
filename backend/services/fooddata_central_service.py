"""Explicit USDA FoodData Central adapter with provenance-preserving responses."""
from __future__ import annotations
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
import requests
from backend.config import APIConfig
from backend.services.base_service import ExternalServiceError
class FoodDataCentralService:
    BASE_URL="https://api.nal.usda.gov/fdc/v1"
    NUTRIENT_ALIASES={"energy":"energy_kcal","energy (atwater general factors)":"energy_kcal","protein":"protein_g","carbohydrate, by difference":"carbohydrate_g","total lipid (fat)":"fat_g","fiber, total dietary":"fiber_g","sugars, total including nlea":"sugars_g","sodium, na":"sodium_mg","calcium, ca":"calcium_mg","iron, fe":"iron_mg","potassium, k":"potassium_mg","vitamin c, total ascorbic acid":"vitamin_c_mg","vitamin d (d2 + d3)":"vitamin_d_mcg"}
    def __init__(self,api_key:Optional[str]=None):
        self.api_key=api_key or APIConfig.FOODDATA_CENTRAL_API_KEY; self.session=requests.Session()
        if not self.api_key: raise ExternalServiceError("FOODDATA_CENTRAL_API_KEY is not configured")
    def _request(self,endpoint:str,*,params:Optional[Dict[str,Any]]=None)->Dict[str,Any]:
        query=dict(params or {}); query["api_key"]=self.api_key; last=None
        for attempt in range(APIConfig.MAX_RETRIES):
            try:
                response=self.session.get(f"{self.BASE_URL}/{endpoint.lstrip('/')}",params=query,headers={"Accept":"application/json"},timeout=APIConfig.REQUEST_TIMEOUT_SECONDS); response.raise_for_status(); payload=response.json()
                if not isinstance(payload,dict): raise ValueError("FoodData Central returned a non-object response")
                return payload
            except (requests.RequestException,ValueError) as exc:
                last=exc
                if attempt+1<APIConfig.MAX_RETRIES: time.sleep(APIConfig.RETRY_BACKOFF_FACTOR*(2**attempt))
        raise ExternalServiceError("FoodData Central request failed") from last
    def search(self,query:str,*,page_size:int=25,data_types:Optional[Iterable[str]]=None)->Dict[str,Any]:
        query=query.strip()
        if not query: raise ValueError("query is required")
        params={"query":query,"pageSize":min(max(int(page_size),1),100)}
        if data_types: params["dataType"]=list(data_types)
        payload=self._request("foods/search",params=params); foods=payload.get("foods",[])
        if not isinstance(foods,list): raise ExternalServiceError("FoodData Central search payload is malformed")
        return {"query":query,"total_hits":int(payload.get("totalHits",len(foods)) or 0),"foods":[self._summary(x) for x in foods if isinstance(x,dict)],"provenance":self._provenance("search")}
    def get_food(self,fdc_id:int)->Dict[str,Any]:
        if fdc_id<=0: raise ValueError("fdc_id must be positive")
        payload=self._request(f"food/{fdc_id}")
        return {**self._summary(payload),"nutrients":self._map_nutrients(payload.get("foodNutrients",[])),"portions":self._map_portions(payload.get("foodPortions",[])),"ingredients":payload.get("ingredients"),"publication_date":payload.get("publicationDate"),"provenance":self._provenance(str(fdc_id)),"raw_data_type":payload.get("dataType")}
    @staticmethod
    def _summary(food:Dict[str,Any])->Dict[str,Any]:
        fdc_id=food.get("fdcId"); return {"fdc_id":int(fdc_id) if isinstance(fdc_id,(int,float,str)) and str(fdc_id).isdigit() else fdc_id,"description":food.get("description"),"data_type":food.get("dataType"),"brand_owner":food.get("brandOwner"),"brand_name":food.get("brandName"),"gtin_upc":food.get("gtinUpc"),"food_category":food.get("foodCategory")}
    def _map_nutrients(self,values:Any)->Dict[str,Dict[str,Any]]:
        result={}
        if not isinstance(values,list): return result
        for entry in values:
            if not isinstance(entry,dict): continue
            nutrient=entry.get("nutrient") if isinstance(entry.get("nutrient"),dict) else entry; name=str(nutrient.get("name") or entry.get("nutrientName") or "").strip(); amount=entry.get("amount") if entry.get("amount") is not None else entry.get("value"); key=self.NUTRIENT_ALIASES.get(name.lower()) or f"fdc:{nutrient.get('id') or entry.get('nutrientId') or name}"
            result[key]={"name":name,"amount":float(amount) if isinstance(amount,(int,float)) else None,"unit":nutrient.get("unitName") or entry.get("unitName"),"nutrient_id":nutrient.get("id") or entry.get("nutrientId"),"derivation":entry.get("foodNutrientDerivation")}
        return result
    @staticmethod
    def _map_portions(values:Any)->List[Dict[str,Any]]:
        if not isinstance(values,list): return []
        return [{"amount":x.get("amount"),"gram_weight":x.get("gramWeight"),"modifier":x.get("modifier"),"measure_unit":(x.get("measureUnit") or {}).get("name") if isinstance(x.get("measureUnit"),dict) else None,"sequence_number":x.get("sequenceNumber")} for x in values if isinstance(x,dict)]
    @staticmethod
    def _provenance(resource:str)->Dict[str,Any]:
        return {"source":"USDA FoodData Central","source_url":"https://fdc.nal.usda.gov/","api_resource":resource,"retrieved_at":datetime.now(timezone.utc).isoformat(),"license":"CC0/public domain","validation_status":"external_source_not_independently_verified"}
