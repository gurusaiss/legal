from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    role = Column(String, nullable=False, default="inspector")  # inspector | admin | auditor
    created_at = Column(DateTime, default=datetime.utcnow)


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    inspector_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    product_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    image_path = Column(String, nullable=False)
    processed_image_path = Column(String, nullable=True)

    rule_version = Column(String, nullable=False)
    pack_date_hint = Column(String, nullable=True)  # user-supplied mfg date used to pick rule version

    pack_width_mm = Column(Float, nullable=True)
    pack_height_mm = Column(Float, nullable=True)
    calibration_confirmed = Column(Boolean, default=False)
    font_check_status = Column(String, default="skipped_no_calibration")  # checked | skipped_no_calibration
    calibration_method = Column(String, default="none")  # marker | manual_edge_assumption | none
    marker_px_per_mm = Column(Float, nullable=True)

    image_quality_score = Column(Float, nullable=True)
    quality_flags = Column(Text, nullable=True)  # JSON string: blur, glare, low_res

    raw_ocr_text = Column(Text, nullable=True)
    extracted_fields = Column(Text, nullable=True)  # JSON string of field -> {value, confidence, bbox}

    status = Column(String, default="processing")  # processing | pass | violation | needs_review
    compliance_score = Column(Float, nullable=True)

    violations = relationship("Violation", back_populates="scan", cascade="all, delete-orphan")
    evidence_items = relationship("Evidence", back_populates="scan", cascade="all, delete-orphan")


class Evidence(Base):
    """Supplementary photos an inspector attaches to a scan after the initial
    upload — e.g. a shelf photo, a close-up of a specific violation, or a
    second angle of a curved pack the first photo didn't capture clearly."""
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False)
    uploaded_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    image_path = Column(String, nullable=False)
    caption = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    scan = relationship("Scan", back_populates="evidence_items")


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    scan_id = Column(Integer, ForeignKey("scans.id"), nullable=False)

    field = Column(String, nullable=False)
    label = Column(String, nullable=False)
    rule_ref = Column(String, nullable=False)
    issue_type = Column(String, nullable=False)  # missing | invalid_format | font_too_small | low_confidence
    detail = Column(Text, nullable=True)
    severity = Column(String, default="high")  # high | medium | low
    confidence = Column(Float, nullable=True)

    scan = relationship("Scan", back_populates="violations")
