"""Generates the printable ArUco calibration marker sheet.

Printed as a PDF (not a raw PNG) because PDF page geometry is defined in
physical units — a PDF viewer's "Actual size / 100%" print option reproduces
the marker at exactly CALIBRATION_MARKER_LENGTH_MM, whereas a browser
printing an <img> tag routinely ignores embedded DPI metadata and rescales
to fit the page. A printed 50mm ruler is included so the inspector can
sanity-check their printer didn't silently rescale the page anyway.
"""
import os

import cv2
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.paths import REPORTS_DIR
from app.services.preprocessing import ARUCO_DICTIONARY, CALIBRATION_MARKER_ID, CALIBRATION_MARKER_LENGTH_MM

MARKER_PDF_PATH = os.path.join(REPORTS_DIR, "calibration_marker.pdf")
_MARKER_PNG_PATH = os.path.join(REPORTS_DIR, "_calibration_marker_raw.png")


def _generate_marker_png() -> str:
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    # Render at a high pixel resolution so it stays crisp when placed into the PDF at mm size.
    # No extra padding here: this image is drawn at exactly CALIBRATION_MARKER_LENGTH_MM in the
    # PDF, so padding it would make the *encoded* marker smaller than that constant assumes.
    # The white page margin around it (from the layout below) serves as the detector's quiet zone.
    marker_img = cv2.aruco.generateImageMarker(dictionary, CALIBRATION_MARKER_ID, 600)
    cv2.imwrite(_MARKER_PNG_PATH, marker_img)
    return _MARKER_PNG_PATH


def generate_marker_pdf(force: bool = False) -> str:
    if os.path.exists(MARKER_PDF_PATH) and not force:
        return MARKER_PDF_PATH

    png_path = _generate_marker_png()

    c = canvas.Canvas(MARKER_PDF_PATH, pagesize=A4)
    page_width, page_height = A4

    c.setFont("Helvetica-Bold", 14)
    c.drawString(20 * mm, page_height - 20 * mm, "Legal Metrology Scanner — Font-Size Calibration Marker")

    c.setFont("Helvetica", 10)
    instructions = [
        "1. Print this page at ACTUAL SIZE / 100% scale — do NOT use 'Fit to page'.",
        "2. Verify the ruler below measures exactly 50mm with a physical ruler after printing.",
        "3. Cut out the marker and place it flat, next to the product, in the same plane as the label.",
        "4. Photograph the product with the marker fully visible and unobstructed.",
        "5. The app detects the marker automatically — no manual pack measurement needed for scale.",
    ]
    y = page_height - 30 * mm
    for line in instructions:
        c.drawString(20 * mm, y, line)
        y -= 6 * mm

    # 50mm scale-check ruler with 5mm ticks.
    ruler_y = y - 10 * mm
    ruler_x0 = 20 * mm
    c.line(ruler_x0, ruler_y, ruler_x0 + 50 * mm, ruler_y)
    for i in range(0, 51, 5):
        tick_h = 4 * mm if i % 10 == 0 else 2 * mm
        c.line(ruler_x0 + i * mm, ruler_y, ruler_x0 + i * mm, ruler_y + tick_h)
    c.setFont("Helvetica", 8)
    c.drawString(ruler_x0, ruler_y - 5 * mm, "0mm")
    c.drawString(ruler_x0 + 50 * mm - 8 * mm, ruler_y - 5 * mm, "50mm")

    # The marker itself, drawn at its true physical size.
    marker_size = CALIBRATION_MARKER_LENGTH_MM * mm
    marker_x = 20 * mm
    marker_y = ruler_y - 20 * mm - marker_size
    c.drawImage(png_path, marker_x, marker_y, width=marker_size, height=marker_size)
    c.setFont("Helvetica", 8)
    c.drawString(marker_x, marker_y - 6 * mm, f"Marker ID {CALIBRATION_MARKER_ID} — {CALIBRATION_MARKER_LENGTH_MM:.0f}mm x {CALIBRATION_MARKER_LENGTH_MM:.0f}mm")

    c.showPage()
    c.save()
    return MARKER_PDF_PATH
