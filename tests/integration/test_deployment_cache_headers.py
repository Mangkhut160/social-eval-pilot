from __future__ import annotations

from pathlib import Path


def test_nginx_marks_root_document_as_non_cacheable() -> None:
    config_path = Path("deploy/nginx/socialeval.conf")
    config = config_path.read_text(encoding="utf-8")

    assert "location = /" in config
    assert 'add_header Cache-Control "no-store, no-cache, must-revalidate"' in config
