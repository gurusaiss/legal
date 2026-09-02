"""Central definition of where uploaded images and generated reports live on
disk. Overridable via env vars so a single mounted volume/disk (Render disk,
Railway volume, etc.) can hold everything that needs to survive a redeploy —
without this, a host with an ephemeral filesystem silently loses every scan's
photos and reports on the next restart.
"""
import os

_BACKEND_ROOT = os.path.dirname(os.path.dirname(__file__))

UPLOADS_DIR = os.environ.get("LM_UPLOADS_DIR", os.path.join(_BACKEND_ROOT, "uploads"))
REPORTS_DIR = os.environ.get("LM_REPORTS_DIR", os.path.join(_BACKEND_ROOT, "reports"))

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(REPORTS_DIR, exist_ok=True)
