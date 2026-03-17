from __future__ import annotations

import re
from typing import Optional, Tuple

import dateparser


YES_PATTERNS = re.compile(r"\b(yes|yeah|yep|we do|we accept|we take)\b", re.IGNORECASE)
NO_PATTERNS = re.compile(r"\b(no|nope|we don't|we do not|not)\b", re.IGNORECASE)


def extract_insurance_ok(transcript: str) -> Optional[bool]:
    if YES_PATTERNS.search(transcript):
        return True
    if NO_PATTERNS.search(transcript):
        return False
    return None


def extract_datetime(transcript: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Very lightweight natural language date/time extraction using dateparser.
    Returns (date_iso, time_str) where date_iso is YYYY-MM-DD.
    """
    dt = dateparser.parse(transcript, settings={"PREFER_DATES_FROM": "future"})
    if not dt:
        return None, None
    return dt.date().isoformat(), dt.strftime("%H:%M")


def extract_provider(transcript: str) -> Optional[str]:
    """
    Naive heuristic: look for 'Dr. <Name>' pattern.
    """
    m = re.search(r"\bDr\.\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)", transcript)
    if m:
        return m.group(0)
    return None

