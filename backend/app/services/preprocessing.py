"""Image preprocessing: quality gate + geometry/lighting cleanup before OCR.

Kept deliberately simple (classic CV, no ML) so it's fast, explainable and
works offline. Flags bad captures instead of silently feeding OCR garbage —
see Risk Register item "Poor image quality" / "Glare".
"""
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np

# The printed calibration marker (see calibration.py) — an ArUco tag of this
# physical side length, placed flat next to the product before photographing.
# Detecting it gives a ground-truth px-per-mm ratio instead of assuming the
# pack fills the frame edge-to-edge (see Risk Register: "Font measurement").
ARUCO_DICTIONARY = cv2.aruco.DICT_4X4_50
CALIBRATION_MARKER_ID = 0
CALIBRATION_MARKER_LENGTH_MM = 30.0


@dataclass
class MarkerCalibration:
    found: bool
    px_per_mm: Optional[float] = None
    marker_id: Optional[int] = None
    corners_px: Optional[list] = None


@dataclass
class QualityReport:
    blur_score: float
    glare_ratio: float
    brightness: float
    resolution_ok: bool
    is_usable: bool
    flags: list = field(default_factory=list)


def _blur_score(gray: np.ndarray) -> float:
    # Variance of Laplacian: higher = sharper.
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _glare_ratio(gray: np.ndarray) -> float:
    # Fraction of near-blown-out pixels (specular highlights on plastic/foil packs).
    overexposed = np.sum(gray > 245)
    return float(overexposed) / gray.size


def assess_quality(image: np.ndarray) -> QualityReport:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]

    blur = _blur_score(gray)
    glare = _glare_ratio(gray)
    brightness = float(np.mean(gray))
    resolution_ok = min(h, w) >= 480

    flags = []
    if blur < 60:
        flags.append("blurry")
    if glare > 0.08:
        flags.append("glare")
    if brightness < 40:
        flags.append("too_dark")
    if brightness > 235:
        flags.append("overexposed")
    if not resolution_ok:
        flags.append("low_resolution")

    is_usable = len(flags) == 0 or (len(flags) == 1 and flags[0] in ("glare",))
    return QualityReport(blur, glare, brightness, resolution_ok, is_usable, flags)


def deskew_and_enhance(image: np.ndarray) -> np.ndarray:
    """Perspective-agnostic cleanup: grayscale, denoise, adaptive contrast,
    and a light deskew based on the dominant text-line angle.
    Full 4-point perspective correction (for strongly curved/angled packs) is
    left as a documented follow-up — see rules/README for scope notes."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    enhanced = clahe.apply(denoised)

    angle = _estimate_skew(enhanced)
    if abs(angle) > 0.5:
        (h, w) = enhanced.shape[:2]
        center = (w // 2, h // 2)
        m = cv2.getRotationMatrix2D(center, angle, 1.0)
        enhanced = cv2.warpAffine(enhanced, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def _estimate_skew(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100, minLineLength=gray.shape[1] // 4, maxLineGap=10)
    if lines is None:
        return 0.0
    angles = []
    for line in lines:
        x1, y1, x2, y2 = line[0]
        if x2 - x1 == 0:
            continue
        angle = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        if -30 < angle < 30:
            angles.append(angle)
    if not angles:
        return 0.0
    return float(np.median(angles))


def detect_reference_marker(image: np.ndarray, marker_length_mm: float = CALIBRATION_MARKER_LENGTH_MM) -> MarkerCalibration:
    """Looks for the printed ArUco calibration marker in-frame. If found,
    returns a ground-truth px-per-mm ratio from the marker's known physical
    side length — this is what makes font-size measurement trustworthy
    rather than a "the pack fills the photo" guess.

    ArUco is used because it's rotation/perspective-tolerant by design (it
    reads its corners directly, not an axis-aligned bounding box), so a
    tilted or off-angle photo doesn't need separate deskewing for this
    measurement to stay accurate.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    dictionary = cv2.aruco.getPredefinedDictionary(ARUCO_DICTIONARY)
    detector_params = cv2.aruco.DetectorParameters()
    detector = cv2.aruco.ArucoDetector(dictionary, detector_params)

    corners, ids, _ = detector.detectMarkers(gray)
    if ids is None or len(ids) == 0:
        return MarkerCalibration(found=False)

    ids_flat = ids.flatten().tolist()
    if CALIBRATION_MARKER_ID not in ids_flat:
        # A different marker was detected (e.g. from an unrelated QR/AR tag
        # in the background) — don't calibrate off a marker we don't recognize.
        return MarkerCalibration(found=False)

    idx = ids_flat.index(CALIBRATION_MARKER_ID)
    marker_corners = corners[idx][0]  # 4x2 array: top-left, top-right, bottom-right, bottom-left

    side_lengths_px = [
        float(np.linalg.norm(marker_corners[i] - marker_corners[(i + 1) % 4]))
        for i in range(4)
    ]
    avg_side_px = float(np.mean(side_lengths_px))
    if avg_side_px <= 0:
        return MarkerCalibration(found=False)

    px_per_mm = avg_side_px / marker_length_mm
    return MarkerCalibration(
        found=True,
        px_per_mm=px_per_mm,
        marker_id=CALIBRATION_MARKER_ID,
        corners_px=marker_corners.tolist(),
    )
