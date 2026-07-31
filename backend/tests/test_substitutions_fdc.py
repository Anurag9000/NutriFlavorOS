from backend.domain.substitutions import suggest_substitutions
from backend.services.fooddata_central_service import FoodDataCentralService


def test_substitution_filters_explicit_allergens_and_prefers_pantry():
    values=suggest_substitutions("milk",allergies=["soy"],dietary_restrictions=["vegan"],pantry_ingredients=["oat milk"])
    replacements=[value.replacement for value in values]
    assert "soy milk" not in replacements
    assert replacements[0]=="oat milk"
    assert all(any("not an allergy" in warning for warning in value.warnings) for value in values)


def test_fdc_mapping_preserves_missing_and_provenance():
    service=FoodDataCentralService.__new__(FoodDataCentralService)
    nutrients=service._map_nutrients([{"nutrient":{"id":1003,"name":"Protein","unitName":"G"},"amount":12.5},{"nutrient":{"id":9999,"name":"Unknown compound","unitName":"MG"}}])
    assert nutrients["protein_g"]["amount"]==12.5
    assert nutrients["fdc:9999"]["amount"] is None
    provenance=service._provenance("123")
    assert provenance["source"]=="USDA FoodData Central"
    assert provenance["validation_status"]=="external_source_not_independently_verified"
