from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from app.models.models import User
from app.services import calibration
from app.services.auth import get_current_user

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.get("/marker.pdf")
def download_marker(user: User = Depends(get_current_user)):
    filepath = calibration.generate_marker_pdf()
    return FileResponse(filepath, media_type="application/pdf", filename="calibration_marker.pdf")
