from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base
from backend.domain.conversions import ConversionRequest
from backend.services.conversion_service import convert_quantity, import_fdc_portions, list_storage_policies, seed_official_storage_policies
from fastapi import HTTPException
import pytest


def _db():
    engine=create_engine("sqlite://",connect_args={"check_same_thread":False},poolclass=StaticPool); Base.metadata.create_all(engine); return sessionmaker(bind=engine)()


def test_fdc_conversion_is_food_specific_and_preserves_missing_evidence():
    db=_db(); count=import_fdc_portions(db,canonical_name="rolled oats",fdc_id=123,portions=[{"amount":0.5,"gramWeight":40,"measureUnit":{"name":"cup"}},{"amount":None,"gramWeight":10,"measureUnit":{"name":"spoon"}}],source_version="2026-04")
    assert count==1
    result=convert_quantity(db,ConversionRequest(canonical_name="rolled oats",quantity_min=1,quantity_max=2,from_unit="cup",to_unit="g"))
    assert result.output_quantity_min==80 and result.output_quantity_max==160
    with pytest.raises(HTTPException):
        convert_quantity(db,ConversionRequest(canonical_name="rice",quantity_min=1,quantity_max=1,from_unit="cup",to_unit="g"))


def test_only_reviewed_storage_policies_are_seeded_with_sources():
    db=_db(); assert seed_official_storage_policies(db)>=1
    rows=list_storage_policies(db,storage_state="refrigerated")
    assert rows and all(row.source_url.startswith("https://") for row in rows)
    assert all(row.duration_max_hours is None or row.duration_max_hours>=row.duration_min_hours for row in rows)
