from __future__ import annotations

import mimetypes
from contextlib import contextmanager
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import urlparse

from fastapi import UploadFile

from src.core.object_storage import get_backend_for_location, get_storage_backend, is_remote_location

ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
UPLOAD_ROOT = Path("data/uploads")


def get_extension(filename: str) -> str:
    return Path(filename).suffix.lower().lstrip(".")


def validate_upload_filename(filename: str) -> str:
    ext = get_extension(filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext or 'unknown'}")
    return ext


async def save_upload_file(file: UploadFile, paper_id: str) -> str:
    ext = validate_upload_filename(file.filename or "")
    content = await file.read()
    content_type = file.content_type or mimetypes.guess_type(file.filename or "")[0] or "application/octet-stream"
    stored = get_storage_backend().put_bytes(
        key=f"uploads/{paper_id}.{ext}",
        content=content,
        content_type=content_type,
    )
    return stored.location


def delete_stored_file(location: str | None) -> None:
    if not location:
        return
    get_backend_for_location(location).delete(location)


@contextmanager
def materialize_input_file(location: str):
    if not is_remote_location(location):
        yield location
        return

    suffix = Path(urlparse(location).path).suffix
    payload = get_backend_for_location(location).get_bytes(location)
    with NamedTemporaryFile(delete=False, suffix=suffix) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)

    try:
        yield str(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)
