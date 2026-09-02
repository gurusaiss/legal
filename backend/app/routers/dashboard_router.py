from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Scan, Violation, User
from app.services.auth import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    total = db.query(func.count(Scan.id)).scalar() or 0
    passed = db.query(func.count(Scan.id)).filter(Scan.status == "pass").scalar() or 0
    violated = db.query(func.count(Scan.id)).filter(Scan.status == "violation").scalar() or 0
    needs_review = db.query(func.count(Scan.id)).filter(Scan.status == "needs_review").scalar() or 0

    top_violation_rows = (
        db.query(Violation.field, Violation.label, func.count(Violation.id).label("cnt"))
        .group_by(Violation.field, Violation.label)
        .order_by(func.count(Violation.id).desc())
        .limit(8)
        .all()
    )

    by_category_rows = (
        db.query(Scan.category, func.count(Scan.id).label("cnt"))
        .group_by(Scan.category)
        .all()
    )

    return {
        "total_scans": total,
        "passed": passed,
        "violations": violated,
        "needs_review": needs_review,
        "compliance_rate": round(passed / total, 2) if total else None,
        "top_violations": [
            {"field": r[0], "label": r[1], "count": r[2]} for r in top_violation_rows
        ],
        "by_category": [
            {"category": r[0] or "Uncategorized", "count": r[1]} for r in by_category_rows
        ],
    }
