"""OCR wrapper. Tesseract is the default (zero external dependency beyond the
binary, easy to demo offline). The interface is deliberately provider-agnostic
so PaddleOCR / Google ML Kit can be swapped in later per the tech evaluation
in the design doc, without touching downstream code.
"""
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from pytesseract import Output


@dataclass
class TextBlock:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float

    @property
    def bbox(self):
        return (self.left, self.top, self.left + self.width, self.top + self.height)


def extract_text_blocks(image: np.ndarray, lang: str = "eng") -> list:
    """Runs OCR and returns word-level blocks with bounding boxes.
    Bounding box height is later used as a proxy for physical font size
    once calibrated against the pack's known dimensions."""
    data = pytesseract.image_to_data(image, lang=lang, output_type=Output.DICT)
    blocks = []
    n = len(data["text"])
    for i in range(n):
        text = data["text"][i].strip()
        conf_raw = data["conf"][i]
        try:
            conf = float(conf_raw)
        except (TypeError, ValueError):
            conf = -1.0
        if not text or conf < 0:
            continue
        blocks.append(TextBlock(
            text=text,
            left=int(data["left"][i]),
            top=int(data["top"][i]),
            width=int(data["width"][i]),
            height=int(data["height"][i]),
            confidence=conf,
        ))
    return blocks


def blocks_to_text(blocks: list) -> str:
    return " ".join(b.text for b in blocks)


def average_confidence(blocks: list) -> float:
    if not blocks:
        return 0.0
    return sum(b.confidence for b in blocks) / len(blocks)
