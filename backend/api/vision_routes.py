from fastapi import APIRouter, File, UploadFile, HTTPException
from typing import Dict, Any
import io
from PIL import Image
from backend.ml.recipe_vision import get_vision_analyzer

router = APIRouter(prefix="/api/v1/vision", tags=["vision"])

@router.post("/analyze")
async def analyze_food_image(image: UploadFile = File(...)):
    """
    Analyze food image using real ResNet50-based computer vision
    """
    if not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image.")
    
    try:
        # Read image bytes
        contents = await image.read()
        pil_image = Image.open(io.BytesIO(contents))
        
        # Get analyzer singleton
        analyzer = get_vision_analyzer()
        
        # Perform analysis
        results = analyzer.analyze_pil_image(pil_image)
        
        return {
            "success": True,
            "data": results,
            "filename": image.filename
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision analysis failed: {str(e)}")
