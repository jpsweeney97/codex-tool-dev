"""Tests for ticket_dedup.py — normalization and fingerprinting."""
from __future__ import annotations


from scripts.ticket_dedup import (
    normalize,
    dedup_fingerprint,
    target_fingerprint,
)


class TestNormalize:
    """Test vectors from the contract."""

    def test_strip_and_collapse_whitespace(self):
        assert normalize("  Hello,  World!  ") == "hello world"

    def test_remove_punctuation_keep_hyphens_underscores(self):
        assert normalize("Fix: the AUTH bug...") == "fix the auth bug"

    def test_unicode_nfc(self):
        # NFC normalization preserves composed forms.
        assert normalize("résumé") == "résumé"

    def test_multiple_spaces_and_newlines(self):
        assert normalize("  multiple   spaces  \n  newlines  ") == "multiple spaces newlines"

    def test_keep_hyphens_and_underscores(self):
        assert normalize("keep-hyphens and_underscores") == "keep-hyphens and_underscores"

    def test_empty_string(self):
        assert normalize("") == ""

    def test_only_punctuation(self):
        assert normalize("!!!...???") == ""


class TestDedupFingerprint:
    def test_deterministic(self):
        fp1 = dedup_fingerprint("Fix the auth bug", ["handler.py", "config.py"])
        fp2 = dedup_fingerprint("Fix the auth bug", ["handler.py", "config.py"])
        assert fp1 == fp2

    def test_sorted_paths(self):
        """Path order doesn't affect fingerprint."""
        fp1 = dedup_fingerprint("bug", ["b.py", "a.py"])
        fp2 = dedup_fingerprint("bug", ["a.py", "b.py"])
        assert fp1 == fp2

    def test_different_text_different_fingerprint(self):
        fp1 = dedup_fingerprint("bug one", ["a.py"])
        fp2 = dedup_fingerprint("bug two", ["a.py"])
        assert fp1 != fp2

    def test_normalization_applied(self):
        """Whitespace/case differences produce same fingerprint."""
        fp1 = dedup_fingerprint("Fix the Bug", ["a.py"])
        fp2 = dedup_fingerprint("  fix  the  bug  ", ["a.py"])
        assert fp1 == fp2

    def test_empty_paths(self):
        fp = dedup_fingerprint("some problem", [])
        assert isinstance(fp, str)
        assert len(fp) == 64  # sha256 hex digest


class TestTargetFingerprint:
    def test_deterministic(self, tmp_path):
        f = tmp_path / "ticket.md"
        f.write_text("# Ticket content", encoding="utf-8")
        fp1 = target_fingerprint(f)
        fp2 = target_fingerprint(f)
        assert fp1 == fp2

    def test_changes_on_content_change(self, tmp_path):
        f = tmp_path / "ticket.md"
        f.write_text("version 1", encoding="utf-8")
        fp1 = target_fingerprint(f)
        f.write_text("version 2", encoding="utf-8")
        fp2 = target_fingerprint(f)
        assert fp1 != fp2

    def test_none_for_nonexistent(self, tmp_path):
        assert target_fingerprint(tmp_path / "missing.md") is None

    def test_none_for_unreadable(self, tmp_path):
        """Returns None if file becomes unreadable between is_file() and read_bytes()."""
        f = tmp_path / "ticket.md"
        f.write_text("content", encoding="utf-8")
        f.chmod(0o000)
        assert target_fingerprint(f) is None
        f.chmod(0o644)  # restore for cleanup
