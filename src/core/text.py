from __future__ import annotations


def sanitize_nul_chars(value):
    if isinstance(value, str):
        return value.replace("\x00", "")
    if isinstance(value, list):
        return [sanitize_nul_chars(item) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_nul_chars(item) for item in value)
    if isinstance(value, dict):
        return {key: sanitize_nul_chars(item) for key, item in value.items()}
    return value
