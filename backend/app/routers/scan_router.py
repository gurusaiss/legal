import json
import os
import uuid
from datetime import date
from typing import Optional

import cv2
import numpy as np
from dateutil import parser as date_parser
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.models import Scan, Violation, Evidence, User
from app.paths import UPLOADS_DIR
from app.services import preprocessing, ocr, field_extractor, rule_engine, report_generator
from app.services.auth import get_current_user, require_role

router = APIRouter(prefix="/scans", tags=["scans"])


def _parse_pack_date(raw: Optional[str]) -> Optional[date]:
    if not raw:
        return None
    try:
        return date_parser.parse(raw).date()
    except (ValueError, OverflowError):
        return None


def _save_upload_image(raw_bytes: bytes, suffix: str, filename_hint: Optional[str]):
    file_id = uuid.uuid4().hex
    ext = os.path.splitext(filename_hint or "upload.jpg")[1] or ".jpg"
    path = os.path.join(UPLOADS_DIR, f"{file_id}_{suffix}{ext}")
    with open(path, "wb") as f:
        f.write(raw_bytes)
    return path


@router.post("")
async def create_scan(
    image: UploadFile = File(...),
    product_name: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    pack_date_hint: Optional[str] = Form(None),
    pack_width_mm: Optional[float] = Form(None),
    pack_height_mm: Optional[float] = Form(None),
    calibration_confirmed: bool = Form(False),
    db: Session = Depends(get_db),
    # Auditors review scans and don't record new ones — scanning is an inspector/admin action.
    user: User = Depends(require_role("inspector", "admin")),
):
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Unsupported image type; use JPEG/PNG/WEBP")

    raw_bytes = await image.read()
    if len(raw_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 15MB)")

    raw_path = _save_upload_image(raw_bytes, "raw", image.filename)
    processed_path = os.path.splitext(raw_path)[0].replace("_raw", "_processed") + ".jpg"

    np_arr = np.frombuffer(raw_bytes, np.uint8)
    cv_image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    if cv_image is None:
        raise HTTPException(status_code=400, detail="Could not decode image")

    quality = preprocessing.assess_quality(cv_image)
    enhanced = preprocessing.deskew_and_enhance(cv_image)
    cv2.imwrite(processed_path, enhanced)

    pack_date = _parse_pack_date(pack_date_hint)
    resolved_rules = rule_engine.select_rule_version(pack_date)
    declarations = rule_engine.declarations_list(resolved_rules)

    blocks = ocr.extract_text_blocks(enhanced)
    raw_text = ocr.blocks_to_text(blocks)
    extracted = field_extractor.extract_fields(blocks, declarations)
    extracted_serializable = {k: v.to_dict() for k, v in extracted.items()}

    compliance = rule_engine.evaluate_compliance(extracted_serializable, resolved_rules)

    # Font-size calibration: prefer the printed ArUco marker (ground-truth
    # px-per-mm, works at any angle) over the manual "pack fills the frame
    # edge-to-edge" assumption, which only kicks in if no marker was found.
    marker = preprocessing.detect_reference_marker(cv_image)
    px_per_mm = None
    calibration_method = "none"
    if marker.found:
        px_per_mm = marker.px_per_mm
        calibration_method = "marker"
    elif calibration_confirmed and pack_width_mm and pack_width_mm > 0:
        px_per_mm = enhanced.shape[1] / pack_width_mm
        calibration_method = "manual_edge_assumption"

    font_check_status = "skipped_no_calibration"
    if px_per_mm and pack_width_mm and pack_height_mm and pack_width_mm > 0 and pack_height_mm > 0:
        pack_area_cm2 = (pack_width_mm / 10) * (pack_height_mm / 10)
        font_violations = rule_engine.evaluate_font_compliance(
            extracted_serializable, resolved_rules, px_per_mm, pack_area_cm2
        )
        font_check_status = "checked"
        if font_violations:
            compliance["violations"].extend(font_violations)
            compliance["status"] = "violation"
            compliance["score"] = round(max(0.0, compliance["score"] - 0.1 * len(font_violations)), 2)
    elif px_per_mm and calibration_method == "marker":
        # Marker gives accurate scale, but the Second Schedule's minimum font
        # height still depends on the pack's surface area — without that we
        # can measure text height in mm but can't pick the right band.
        font_check_status = "skipped_no_pack_dimensions"

    scan = Scan(
        inspector_id=user.id,
        product_name=product_name,
        category=category,
        image_path=raw_path,
        processed_image_path=processed_path,
        rule_version=compliance["rule_version"],
        pack_date_hint=pack_date_hint,
        pack_width_mm=pack_width_mm,
        pack_height_mm=pack_height_mm,
        calibration_confirmed=bool(calibration_confirmed),
        font_check_status=font_check_status,
        calibration_method=calibration_method,
        marker_px_per_mm=marker.px_per_mm if marker.found else None,
        image_quality_score=quality.blur_score,
        quality_flags=json.dumps(quality.flags),
        raw_ocr_text=raw_text,
        extracted_fields=json.dumps(extracted_serializable),
        status=compliance["status"],
        compliance_score=compliance["score"],
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    for v in compliance["violations"]:
        db.add(Violation(scan_id=scan.id, **v))
    db.commit()

    return _scan_response(scan, compliance["violations"], quality.flags)


def _scan_response(scan: Scan, violations: list, quality_flags: list):
    return {
        "id": scan.id,
        "status": scan.status,
        "compliance_score": scan.compliance_score,
        "rule_version": scan.rule_version,
        "product_name": scan.product_name,
        "category": scan.category,
        "created_at": scan.created_at.isoformat() if scan.created_at else None,
        "quality_flags": quality_flags,
        "extracted_fields": json.loads(scan.extracted_fields) if scan.extracted_fields else {},
        "violations": violations,
        "font_check_status": scan.font_check_status,
        "calibration_method": scan.calibration_method,
        "marker_px_per_mm": scan.marker_px_per_mm,
        "pack_width_mm": scan.pack_width_mm,
        "pack_height_mm": scan.pack_height_mm,
        "image_url": f"/scans/{scan.id}/image" if scan.processed_image_path else None,
        "evidence": [
            {"id": e.id, "caption": e.caption, "created_at": e.created_at.isoformat() if e.created_at else None,
             "image_url": f"/scans/{scan.id}/evidence/{e.id}/image"}
            for e in scan.evidence_items
        ],
    }


@router.get("/{scan_id}")
def get_scan(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    violations = [
        {
            "field": v.field, "label": v.label, "rule_ref": v.rule_ref,
            "issue_type": v.issue_type, "detail": v.detail,
            "severity": v.severity, "confidence": v.confidence,
        }
        for v in scan.violations
    ]
    quality_flags = json.loads(scan.quality_flags) if scan.quality_flags else []
    return _scan_response(scan, violations, quality_flags)


@router.get("")
def list_scans(
    status_filter: Optional[str] = None,
    q: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Scan).order_by(Scan.created_at.desc())
    if status_filter:
        query = query.filter(Scan.status == status_filter)
    if q:
        like = f"%{q}%"
        query = query.filter(or_(
            Scan.product_name.ilike(like),
            Scan.category.ilike(like),
            Scan.raw_ocr_text.ilike(like),
        ))
    scans = query.limit(min(limit, 200)).all()
    return [
        {
            "id": s.id,
            "product_name": s.product_name,
            "category": s.category,
            "status": s.status,
            "compliance_score": s.compliance_score,
            "rule_version": s.rule_version,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in scans
    ]


@router.get("/{scan_id}/image")
def get_scan_image(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan or not scan.processed_image_path or not os.path.exists(scan.processed_image_path):
        raise HTTPException(status_code=404, detail="Image not found")
    return FileResponse(scan.processed_image_path, media_type="image/jpeg")


@router.post("/{scan_id}/evidence")
async def add_evidence(
    scan_id: int,
    image: UploadFile = File(...),
    caption: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("inspector", "admin")),
):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Unsupported image type; use JPEG/PNG/WEBP")

    raw_bytes = await image.read()
    if len(raw_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large (max 15MB)")

    path = _save_upload_image(raw_bytes, "evidence", image.filename)
    evidence = Evidence(scan_id=scan.id, uploaded_by=user.id, image_path=path, caption=caption)
    db.add(evidence)
    db.commit()
    db.refresh(evidence)

    return {
        "id": evidence.id,
        "caption": evidence.caption,
        "created_at": evidence.created_at.isoformat() if evidence.created_at else None,
        "image_url": f"/scans/{scan.id}/evidence/{evidence.id}/image",
    }


@router.get("/{scan_id}/evidence/{evidence_id}/image")
def get_evidence_image(scan_id: int, evidence_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    evidence = db.query(Evidence).filter(Evidence.id == evidence_id, Evidence.scan_id == scan_id).first()
    if not evidence or not os.path.exists(evidence.image_path):
        raise HTTPException(status_code=404, detail="Evidence image not found")
    return FileResponse(evidence.image_path, media_type="image/jpeg")


@router.get("/{scan_id}/report")
def download_report(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    violations = _violation_dicts(scan)
    filepath = report_generator.generate_compliance_pdf(scan, violations)
    return FileResponse(filepath, media_type="application/pdf", filename=os.path.basename(filepath))


@router.get("/{scan_id}/report/editable")
def download_editable_report(scan_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    scan = db.query(Scan).filter(Scan.id == scan_id).first()
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")
    violations = _violation_dicts(scan)
    filepath = report_generator.generate_compliance_docx(scan, violations)
    return FileResponse(
        filepath,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=os.path.basename(filepath),
    )


def _violation_dicts(scan: Scan) -> list:
    return [
        {
            "field": v.field, "label": v.label, "rule_ref": v.rule_ref,
            "issue_type": v.issue_type, "detail": v.detail,
            "severity": v.severity, "confidence": v.confidence,
        }
        for v in scan.violations
    ]
