"""
Utility Helpers
General-purpose utility functions used across the application.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Text Utilities
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Normalize raw extracted text:
    - Normalize unicode characters
    - Collapse excessive whitespace
    - Remove null bytes and control characters
    """
    # Normalize unicode
    text = unicodedata.normalize("NFKD", text)
    # Remove null bytes and control chars (except newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Collapse multiple blank lines into a single blank line
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse multiple spaces (but preserve newlines)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def truncate(text: str, max_chars: int = 500, suffix: str = "…") -> str:
    """Truncate text to max_chars, appending suffix if truncated."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + suffix


def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing unsafe characters.
    Replaces spaces with underscores, strips path traversal sequences.
    """
    # Remove path traversal components
    filename = filename.replace("..", "").replace("/", "").replace("\\", "")
    # Replace spaces
    filename = filename.replace(" ", "_")
    # Allow only alphanumeric, dash, underscore, dot
    filename = re.sub(r"[^a-zA-Z0-9\-_.]", "", filename)
    return filename or "upload"


# ---------------------------------------------------------------------------
# Validation Utilities
# ---------------------------------------------------------------------------

def is_valid_pdf_bytes(data: bytes) -> bool:
    """Quick magic-byte check for PDF files."""
    return data[:4] == b"%PDF"


def is_non_empty_string(value: Any) -> bool:
    """Return True if value is a non-empty, non-whitespace string."""
    return isinstance(value, str) and bool(value.strip())


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp integer value to [min_val, max_val]."""
    return max(min_val, min(max_val, value))


# ---------------------------------------------------------------------------
# Data Utilities
# ---------------------------------------------------------------------------

def flatten_list(nested: List[Any]) -> List[Any]:
    """Flatten one level of nesting in a list."""
    result = []
    for item in nested:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    return result


def deduplicate(items: List[str]) -> List[str]:
    """Remove duplicates from a list while preserving order."""
    seen: set = set()
    result = []
    for item in items:
        key = item.strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def safe_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict keys, returning default if any key is missing."""
    current = d
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


# ---------------------------------------------------------------------------
# Hashing / Fingerprinting
# ---------------------------------------------------------------------------

def sha256_hex(data: bytes) -> str:
    """Return the SHA-256 hex digest of bytes (useful for deduplication)."""
    return hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# Time Utilities
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def format_datetime(dt: Optional[datetime] = None) -> str:
    """Format a datetime (or now) as a human-readable report timestamp."""
    target = dt or datetime.now()
    return target.strftime("%B %d, %Y at %H:%M UTC")
