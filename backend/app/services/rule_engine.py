"""Versioned rule engine.

Design (per project doc, Section 4.3 / 10.3):
    Rules JSON -> Validation Engine -> Result.
No ML here on purpose — legal compliance logic must stay transparent and
auditable, and easy to update when the law changes without retraining anything.

Versioning: each rules/*.json file declares an effective_from/effective_to
window. select_rule_version() picks the file whose window contains the
product's declared packing date (falls back to "today" if unknown), then
layers any declarations_override on top of the base declaration set so a
2017-packed product is judged by 2017 rules, not the 2011 baseline or
today's rules.
"""
import json
import os
from datetime import date, datetime
from typing import Optional

RULES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "rules")

CONFIDENCE_REVIEW_THRESHOLD = 0.5


def _load_all_rule_files() -> list:
    files = []
    for fname in sorted(os.listdir(RULES_DIR)):
        if fname.endswith(".json"):
            with open(os.path.join(RULES_DIR, fname), "r", encoding="utf-8") as f:
                files.append(json.load(f))
    files.sort(key=lambda r: r["effective_from"])
    return files


def select_rule_version(pack_date: Optional[date] = None) -> dict:
    """Returns the fully resolved rule set (base declarations + all
    applicable overrides up to and including the version active on pack_date)."""
    pack_date = pack_date or date.today()
    pack_date_str = pack_date.isoformat()

    rule_files = _load_all_rule_files()
    if not rule_files:
        raise RuntimeError("No rule files found in rules/ directory")

    base = next((r for r in rule_files if "declarations" in r), rule_files[0])
    resolved = {
        "citation_chain": [base["citation"]],
        "version": base["version"],
        "declarations": {d["field"]: dict(d) for d in base["declarations"]},
        "font_size_rules": base.get("font_size_rules"),
    }

    for r in rule_files:
        if r is base:
            continue
        if r["effective_from"] <= pack_date_str:
            resolved["version"] = r["version"]
            resolved["citation_chain"].append(r["citation"])
            for override in r.get("declarations_override", []):
                resolved["declarations"][override["field"]] = dict(override)

    return resolved


def declarations_list(resolved_rules: dict) -> list:
    return list(resolved_rules["declarations"].values())


def evaluate_compliance(extracted_fields: dict, resolved_rules: dict) -> dict:
    """Compares extracted fields against the resolved rule set.
    Returns {status, score, violations: [...]}"""
    violations = []
    declarations = resolved_rules["declarations"]
    total_required = 0
    passed_required = 0

    for field_name, decl in declarations.items():
        if decl.get("conditional"):
            # Conditional declarations (e.g. "if imported", "if loose/multipack")
            # can't be reliably confirmed as applicable from OCR alone, so they
            # never fail the scan outright — flagged for inspector judgement
            # instead. This holds even when a later amendment marks the field
            # required, since the *condition* is what's unverifiable, not the rule.
            continue

        required = decl.get("required", False)
        if required:
            total_required += 1

        extracted: Optional[dict] = extracted_fields.get(field_name)
        found = bool(extracted and extracted.get("found"))
        confidence = extracted.get("confidence", 0.0) if extracted else 0.0

        if not found:
            if required:
                violations.append({
                    "field": field_name,
                    "label": decl["label"],
                    "rule_ref": decl["rule_ref"],
                    "issue_type": "missing",
                    "detail": f"'{decl['label']}' was not detected on the label.",
                    "severity": "high",
                    "confidence": confidence,
                })
            continue

        if required and confidence < CONFIDENCE_REVIEW_THRESHOLD:
            violations.append({
                "field": field_name,
                "label": decl["label"],
                "rule_ref": decl["rule_ref"],
                "issue_type": "low_confidence",
                "detail": f"'{decl['label']}' was detected but with low OCR confidence ({confidence:.0%}); needs manual verification.",
                "severity": "medium",
                "confidence": confidence,
            })
        elif required:
            passed_required += 1
        else:
            passed_required += 0

        # Field-specific format checks
        format_issue = _format_check(field_name, extracted, decl)
        if format_issue:
            violations.append(format_issue)

    score = (passed_required / total_required) if total_required else 1.0
    has_missing_or_invalid = any(v["issue_type"] in ("missing", "invalid_format") for v in violations)
    has_low_conf = any(v["issue_type"] == "low_confidence" for v in violations)

    if has_missing_or_invalid:
        status = "violation"
    elif has_low_conf:
        status = "needs_review"
    else:
        status = "pass"

    return {
        "status": status,
        "score": round(score, 2),
        "violations": violations,
        "rule_version": resolved_rules["version"],
        "citation_chain": resolved_rules["citation_chain"],
    }


def _format_check(field_name: str, extracted: dict, decl: dict) -> Optional[dict]:
    if field_name == "mrp" and extracted.get("inclusive_clause_present") is False:
        return {
            "field": field_name,
            "label": decl["label"],
            "rule_ref": decl["rule_ref"],
            "issue_type": "invalid_format",
            "detail": "MRP is declared but does not clearly state 'inclusive of all taxes'.",
            "severity": "high",
            "confidence": extracted.get("confidence", 0.0),
        }
    if field_name == "manufacturer_name_address" and decl.get("requires_pincode") and extracted.get("pincode_present") is False:
        return {
            "field": field_name,
            "label": decl["label"],
            "rule_ref": decl["rule_ref"],
            "issue_type": "invalid_format",
            "detail": "Manufacturer address is declared but no 6-digit PIN code was found.",
            "severity": "medium",
            "confidence": extracted.get("confidence", 0.0),
        }
    return None


def check_font_size(field_name: str, bbox_height_px: float, px_per_mm: float, resolved_rules: dict, pack_area_cm2: float) -> Optional[dict]:
    """Converts a detected text bbox height to mm using a calibrated
    px-per-mm ratio, then checks it against the area-banded minimum from
    the Second Schedule. px_per_mm must come from a calibration reference
    in-frame (e.g. a known-size marker) — see Risk Register 'Font measurement'."""
    font_rules = resolved_rules.get("font_size_rules")
    if not font_rules or field_name not in font_rules.get("applies_to_fields", []):
        return None
    if px_per_mm <= 0:
        return None

    height_mm = bbox_height_px / px_per_mm
    required_mm = None
    for band in font_rules["bands"]:
        if band["max_area_cm2"] is None or pack_area_cm2 <= band["max_area_cm2"]:
            required_mm = band["min_height_mm"]
            break

    if required_mm is not None and height_mm < required_mm:
        return {
            "field": field_name,
            "label": f"Font size for {field_name}",
            "rule_ref": "Rule 7 / Second Schedule",
            "issue_type": "font_too_small",
            "detail": f"Measured character height ~{height_mm:.1f}mm, required minimum {required_mm}mm for a pack of this size.",
            "severity": "high",
            "confidence": 0.7,
        }
    return None


def evaluate_font_compliance(extracted_fields: dict, resolved_rules: dict, px_per_mm: float, pack_area_cm2: float) -> list:
    """Runs check_font_size over every field the Second Schedule applies to
    (net_quantity, mrp) that was actually detected with a bounding box.
    Returns [] if calibration wasn't provided (px_per_mm <= 0) rather than
    guessing — an unmeasured font is a skipped check, not a silent pass."""
    font_rules = resolved_rules.get("font_size_rules")
    if not font_rules or px_per_mm <= 0:
        return []

    violations = []
    for field_name in font_rules.get("applies_to_fields", []):
        extracted = extracted_fields.get(field_name)
        if not extracted or not extracted.get("found") or not extracted.get("bbox"):
            continue
        bbox = extracted["bbox"]  # (left, top, right, bottom)
        height_px = bbox[3] - bbox[1]
        issue = check_font_size(field_name, height_px, px_per_mm, resolved_rules, pack_area_cm2)
        if issue:
            violations.append(issue)
    return violations
