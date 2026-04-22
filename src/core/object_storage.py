from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from src.core.config import settings

DATA_ROOT = Path("data")


@dataclass(frozen=True)
class StoredObject:
    location: str
    key: str


class StorageBackend(Protocol):
    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> StoredObject: ...

    def get_bytes(self, location: str) -> bytes: ...

    def delete(self, location: str) -> None: ...


class LocalStorageBackend:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or DATA_ROOT

    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        destination = self.root / key
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return StoredObject(location=str(destination), key=key)

    def get_bytes(self, location: str) -> bytes:
        return Path(location).read_bytes()

    def delete(self, location: str) -> None:
        Path(location).unlink(missing_ok=True)


class S3StorageBackend:
    def __init__(self) -> None:
        if not settings.object_storage_bucket:
            raise ValueError("OBJECT_STORAGE_BUCKET must be configured for s3 storage")
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("boto3 is required for s3 object storage") from exc

        self.bucket = settings.object_storage_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint or None,
            region_name=settings.object_storage_region or None,
            aws_access_key_id=settings.object_storage_access_key or None,
            aws_secret_access_key=settings.object_storage_secret_key or None,
        )

    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        put_kwargs = {
            "Bucket": self.bucket,
            "Key": key,
            "Body": content,
        }
        if content_type:
            put_kwargs["ContentType"] = content_type
        self.client.put_object(**put_kwargs)
        return StoredObject(location=f"s3://{self.bucket}/{key}", key=key)

    def get_bytes(self, location: str) -> bytes:
        bucket, key = parse_s3_location(location)
        response = self.client.get_object(Bucket=bucket, Key=key)
        body = response["Body"].read()
        response["Body"].close()
        return body

    def delete(self, location: str) -> None:
        bucket, key = parse_s3_location(location)
        self.client.delete_object(Bucket=bucket, Key=key)


def parse_s3_location(location: str) -> tuple[str, str]:
    parsed = urlparse(location)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Unsupported object storage location: {location}")
    return parsed.netloc, parsed.path.lstrip("/")


def is_remote_location(location: str) -> bool:
    return location.startswith("s3://")


def get_storage_backend() -> StorageBackend:
    backend = settings.object_storage_backend.lower()
    if backend == "local":
        return LocalStorageBackend()
    if backend == "s3":
        return S3StorageBackend()
    raise ValueError(f"Unsupported object storage backend: {settings.object_storage_backend}")


def get_backend_for_location(location: str) -> StorageBackend:
    if is_remote_location(location):
        return S3StorageBackend()
    return LocalStorageBackend()
