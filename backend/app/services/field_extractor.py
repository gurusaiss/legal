"""Turns raw OCR word blocks into the structured fields the rule engine
needs: MRP, net quantity, manufacture date, manufacturer/address, consumer
care, country of origin. Regex + keyword-window matching — deliberately
simple and auditable rather than a black-box NER model, per the design
doc's "rule engine stays simple/transparent" principle. Each extracted
field carries a confidence score so low-confidence hits get routed to
human review instead of being silently trusted (see Risk: "False violation").
"""
import re
from dataclasses import dataclass, asdict
from typing import Optional

from app.services.ocr import TextBlock

MRP_PATTERN = re.compile(r"(?:rs\.?|inr|₹)\s?(\d+(?:[.,]\d{1,2})?)", re.IGNORECASE)
QUANTITY_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s?(kg|g|gm|gms|ml|l|litre|litres|mg|n|pcs|pieces)\b", re.IGNORECASE)
DATE_PATTERN = re.compile(
    r"(\b\d{1,2}[/\-.]\d{4}\b)|(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*[\s\-,]?\d{2,4}\b)|(\b\d{2}[/\-.]\d{2}[/\-.]\d{2,4}\b)",
    re.IGNORECASE,
)
PINCODE_PATTERN = re.compile(r"\b\d{6}\b")
PHONE_OR_EMAIL_PATTERN = re.compile(r"(\b\d{10}\b)|([\w.+-]+@[\w-]+\.[\w.-]+)|(1800[-\s]?\d{3,7})")

KEYWORD_WINDOW_CHARS = 60


@dataclass
class ExtractedField:
    field: str
    value: Optional[str]
    confidence: float  # 0-1
    source_snippet: Optional[str] = None
    bbox: Optional[tuple] = None
    found: bool = False

    def to_dict(self):
        d = asdict(self)
        return d


def _full_text_with_index(blocks: list):
    """Builds a single lowercase string plus an index mapping char offsets
    back to the originating block, so a regex match can recover a bbox."""
    parts = []
    index_map = []  # (start_offset, end_offset, block)
    cursor = 0
    for b in blocks:
        parts.append(b.text)
        start = cursor
        end = cursor + len(b.text)
        index_map.append((start, end, b))
        cursor = end + 1  # + space
    text = " ".join(parts)
    return text, index_map


def _bbox_for_offset(offset: int, index_map: list):
    for start, end, block in index_map:
        if start <= offset <= end:
            return block.bbox
    return None


def _keyword_hit(text_lower: str, keywords: list) -> Optional[int]:
    for kw in keywords:
        idx = text_lower.find(kw.lower())
        if idx != -1:
            return idx
    return None


def extract_fields(blocks: list, rule_declarations: list) -> dict:
    text, index_map = _full_text_with_index(blocks)
    text_lower = text.lower()

    results = {}

    for decl in rule_declarations:
        field = decl["field"]
        keywords = decl.get("keywords", [])
        f_type = decl.get("type", "text")

        if f_type == "price" and field == "mrp":
            results[field] = _extract_mrp(text, text_lower, index_map, decl)
        elif f_type == "quantity":
            results[field] = _extract_quantity(text, text_lower, index_map)
        elif f_type == "date":
            results[field] = _extract_date(text, text_lower, index_map, keywords, field, decl.get("label", field))
        elif field == "manufacturer_name_address":
            results[field] = _extract_manufacturer(text, text_lower, index_map, keywords, decl)
        elif field == "consumer_care":
            results[field] = _extract_consumer_care(text, text_lower, index_map, keywords)
        else:
            results[field] = _extract_generic_keyword(text, text_lower, index_map, keywords, field)

    return results


def _extract_mrp(text, text_lower, index_map, decl) -> ExtractedField:
    m = MRP_PATTERN.search(text)
    if not m:
        return ExtractedField("mrp", None, 0.0, found=False)

    value = m.group(1)
    bbox = _bbox_for_offset(m.start(), index_map)
    must_contain = decl.get("must_contain", [])
    window = text_lower[max(0, m.start() - KEYWORD_WINDOW_CHARS): m.end() + KEYWORD_WINDOW_CHARS]
    has_inclusive_clause = any(phrase in window for phrase in must_contain) if must_contain else True

    confidence = 0.9 if has_inclusive_clause else 0.55
    snippet = text[max(0, m.start() - 20): m.end() + 20]
    field = ExtractedField("mrp", value, confidence, snippet, bbox, found=True)
    field.__dict__["inclusive_clause_present"] = has_inclusive_clause
    return field


def _extract_quantity(text, text_lower, index_map) -> ExtractedField:
    m = QUANTITY_PATTERN.search(text)
    if not m:
        return ExtractedField("net_quantity", None, 0.0, found=False)
    value = f"{m.group(1)} {m.group(2)}"
    bbox = _bbox_for_offset(m.start(), index_map)
    snippet = text[max(0, m.start() - 20): m.end() + 20]
    return ExtractedField("net_quantity", value, 0.85, snippet, bbox, found=True)


def _extract_date(text, text_lower, index_map, keywords, field_name, label) -> ExtractedField:
    kw_idx = _keyword_hit(text_lower, keywords)
    search_region = text
    offset_shift = 0
    if kw_idx is not None:
        start = max(0, kw_idx - 5)
        end = min(len(text), kw_idx + KEYWORD_WINDOW_CHARS)
        search_region = text[start:end]
        offset_shift = start

    m = DATE_PATTERN.search(search_region)
    if not m:
        # Fall back to a whole-document date search — lower confidence
        # since we can't be sure which declaration it belongs to.
        m2 = DATE_PATTERN.search(text)
        if not m2:
            return ExtractedField(field_name, None, 0.0, found=False)
        bbox = _bbox_for_offset(m2.start(), index_map)
        return ExtractedField(field_name, m2.group(0), 0.4, text[max(0, m2.start() - 15):m2.end() + 15], bbox, found=True)

    abs_start = offset_shift + m.start()
    bbox = _bbox_for_offset(abs_start, index_map)
    confidence = 0.9 if kw_idx is not None else 0.5
    return ExtractedField(field_name, m.group(0), confidence, search_region[max(0, m.start() - 15):m.end() + 15], bbox, found=True)


def _extract_manufacturer(text, text_lower, index_map, keywords, decl) -> ExtractedField:
    kw_idx = _keyword_hit(text_lower, keywords)
    if kw_idx is None:
        return ExtractedField("manufacturer_name_address", None, 0.0, found=False)

    end = min(len(text), kw_idx + 120)
    snippet = text[kw_idx:end]
    bbox = _bbox_for_offset(kw_idx, index_map)

    min_len = decl.get("min_length", 8)
    confidence = 0.75 if len(snippet.strip()) >= min_len else 0.4

    if decl.get("requires_pincode"):
        has_pin = bool(PINCODE_PATTERN.search(snippet))
        confidence = confidence if has_pin else confidence * 0.6
        field = ExtractedField("manufacturer_name_address", snippet.strip(), confidence, snippet, bbox, found=True)
        field.__dict__["pincode_present"] = has_pin
        return field

    return ExtractedField("manufacturer_name_address", snippet.strip(), confidence, snippet, bbox, found=True)


def _extract_consumer_care(text, text_lower, index_map, keywords) -> ExtractedField:
    kw_idx = _keyword_hit(text_lower, keywords)
    contact_match = PHONE_OR_EMAIL_PATTERN.search(text)

    if kw_idx is None and not contact_match:
        return ExtractedField("consumer_care", None, 0.0, found=False)

    if kw_idx is not None:
        end = min(len(text), kw_idx + 100)
        snippet = text[kw_idx:end]
        bbox = _bbox_for_offset(kw_idx, index_map)
        confidence = 0.85 if contact_match else 0.55
        return ExtractedField("consumer_care", snippet.strip(), confidence, snippet, bbox, found=True)

    # Only a bare phone/email found, no explicit "consumer care" label nearby.
    bbox = _bbox_for_offset(contact_match.start(), index_map)
    return ExtractedField("consumer_care", contact_match.group(0), 0.45, contact_match.group(0), bbox, found=True)


def _extract_generic_keyword(text, text_lower, index_map, keywords, field_name) -> ExtractedField:
    kw_idx = _keyword_hit(text_lower, keywords) if keywords else None
    if kw_idx is not None:
        end = min(len(text), kw_idx + 80)
        snippet = text[kw_idx:end]
        bbox = _bbox_for_offset(kw_idx, index_map)
        return ExtractedField(field_name, snippet.strip(), 0.6, snippet, bbox, found=True)

    if field_name == "common_name":
        # No reliable "Common Name:" prefix on most real labels — the product
        # name is usually just the largest/most prominent text block instead.
        # Low-confidence heuristic: flag for human confirmation rather than a
        # silent guess (see Risk: "False violation").
        candidates = [block for _, _, block in index_map if len(block.text) >= 3 and not block.text.isdigit()]
        if candidates:
            biggest = max(candidates, key=lambda b: b.height)
            return ExtractedField(field_name, biggest.text, 0.35, biggest.text, biggest.bbox, found=True)

    return ExtractedField(field_name, None, 0.0, found=False)
