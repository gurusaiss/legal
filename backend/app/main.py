import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.models import models  # noqa: F401 -- ensures models are registered before create_all
from app.routers import auth_router, scan_router, dashboard_router, calibration_router

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Legal Metrology Compliance Scanner",
    description="Scans packaged-commodity labels and checks compliance against the "
                "Legal Metrology (Packaged Commodities) Rules, 2011 and its amendments.",
    version="0.1.0",
)

# Comma-separated list of allowed origins for the deployed frontend, e.g.
# "https://your-app.vercel.app,https://your-custom-domain.com" — set via
# LM_ALLOWED_ORIGINS in production. Falls back to the local dev origins so
# nothing extra is needed to run this locally.
_extra_origins = [o.strip() for o in os.environ.get("LM_ALLOWED_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", *_extra_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(scan_router.router)
app.include_router(dashboard_router.router)
app.include_router(calibration_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}
