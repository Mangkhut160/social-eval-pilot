from __future__ import annotations

from src.core.text import sanitize_nul_chars


def test_sanitize_nul_chars_strips_nul_from_nested_strings() -> None:
    payload = {
        "title": "Kimi\x00Linear",
        "quotes": ["alpha\x00beta", "gamma"],
        "meta": {"summary": "delta\x00epsilon"},
    }

    assert sanitize_nul_chars(payload) == {
        "title": "KimiLinear",
        "quotes": ["alphabeta", "gamma"],
        "meta": {"summary": "deltaepsilon"},
    }


def test_sanitize_nul_chars_leaves_non_string_values_unchanged() -> None:
    payload = {
        "score": 91.2,
        "flags": [True, False],
        "nested": {"count": 3},
    }

    assert sanitize_nul_chars(payload) == payload
