"""Generates a synthetic product label image and runs it through the full
pipeline (preprocess -> OCR -> extract -> rule engine) without needing the
HTTP layer. Useful for a fast sanity check during development."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import cv2
import numpy as np

from app.services import preprocessing, ocr, field_extractor, rule_engine


def make_label_image(lines, size=(700, 500)) -> np.ndarray:
    img = np.full((size[1], size[0], 3), 255, dtype=np.uint8)
    y = 40
    for line in lines:
        cv2.putText(img, line, (20, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
        y += 35
    return img


def run_case(name, lines, pack_date=None):
    print(f"\n=== {name} ===")
    img = make_label_image(lines)
    quality = preprocessing.assess_quality(img)
    enhanced = preprocessing.deskew_and_enhance(img)

    resolved = rule_engine.select_rule_version(pack_date)
    declarations = rule_engine.declarations_list(resolved)

    blocks = ocr.extract_text_blocks(enhanced)
    text = ocr.blocks_to_text(blocks)
    print("OCR text:", text)

    extracted = field_extractor.extract_fields(blocks, declarations)
    extracted_dict = {k: v.to_dict() for k, v in extracted.items()}

    result = rule_engine.evaluate_compliance(extracted_dict, resolved)
    print("Status:", result["status"], "| Score:", result["score"], "| Rule version:", result["rule_version"])
    for v in result["violations"]:
        print(f"  - [{v['severity']}] {v['label']} ({v['rule_ref']}): {v['detail']}")


if __name__ == "__main__":
    run_case(
        "Fully compliant label",
        [
            "Marketed by: ABC Foods Pvt Ltd, MG Road, Bengaluru 560001",
            "Common Name: Refined Sunflower Oil",
            "Net Wt: 500 g",
            "MRP Rs. 145.00 Incl. of all taxes",
            "Mfg Date: 03/2026",
            "Consumer Care: care@abcfoods.com 1800-123-4567",
        ],
    )

    run_case(
        "Missing MRP and consumer care",
        [
            "Marketed by: XYZ Snacks, Pune 411001",
            "Common Name: Potato Chips",
            "Net Wt: 100 g",
            "Mfg Date: Jan 2026",
        ],
    )
