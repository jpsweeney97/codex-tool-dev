"""Dedup normalization and fingerprinting.

normalize() implements the 5-step canonical normalization from the contract.
dedup_fingerprint() produces the sha256 fingerprint for dedup detection.
target_fingerprint() produces the TOCTOU fingerprint for a ticket file.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path


def normalize(text: str) -> str:
    """Canonical 5-step normalization for dedup fingerprinting.

    Steps:
    1. Strip leading/trailing whitespace
    2. Collapse all internal whitespace sequences to single space
    3. Lowercase
    4. Remove punctuation except hyphens and underscores
    5. NFC Unicode normalization
    """
    # Step 1: Strip.
    text = text.strip()
    # Step 2: Collapse whitespace.
    text = re.sub(r"\s+", " ", text)
    # Step 3: Lowercase.
    text = text.lower()
    # Step 4: Remove punctuation except hyphens and underscores.
    # Keep: alphanumeric, spaces, hyphens, underscores.
    text = re.sub(r"[^\w\s-]", "", text)
    # \w includes underscores. Collapse any resulting double spaces.
    text = re.sub(r"\s+", " ", text).strip()
    # Step 5: NFC Unicode normalization.
    text = unicodedata.normalize("NFC", text)
    return text


def dedup_fingerprint(problem_text: str, key_file_paths: list[str]) -> str:
    """Generate a dedup fingerprint: sha256(normalize(problem_text) + "|" + sorted(paths)).

    Used during `plan` stage to detect duplicate tickets within 24-hour window.
    """
    normalized = normalize(problem_text)
    sorted_paths = sorted(key_file_paths)
    payload = normalized + "|" + ",".join(sorted_paths)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def target_fingerprint(ticket_path: Path) -> str | None:
    """Generate a TOCTOU fingerprint: sha256(content + mtime).

    Used before execute to verify ticket wasn't modified since plan/read.
    Returns None if file doesn't exist.
    """
    if not ticket_path.is_file():
        return None
    try:
        content = ticket_path.read_bytes()
        mtime = str(ticket_path.stat().st_mtime)
    except OSError:
        return None
    payload = content + mtime.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
