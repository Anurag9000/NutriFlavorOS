"""Food-image analysis endpoint.

The repository does not contain a validated food-recognition checkpoint. The
previous route returned random classification and nutrient heads from an
ImageNet backbone. It is intentionally disabled rather than emitting plausible
but unsupported nutrition results.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from backend.database import DBUser
from backend.utils.security import get_current_user


router = APIRouter(prefix="/api/v1/vision", tags=["vision"])


@router.post("/analyze")
async def analyze_food_image(
    image: UploadFile = File(...),
    _: DBUser = Depends(get_current_user),
):
    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File provided is not an image")

    contents = await image.read(5 * 1024 * 1024 + 1)
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image exceeds the 5 MB limit")

    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Food-image analysis is disabled until a validated checkpoint and calibration report are available",
    )
