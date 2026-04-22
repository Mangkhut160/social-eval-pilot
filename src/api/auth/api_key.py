from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime

from sqlalchemy.orm import Session

from src.core.time import utc_now
from src.models.api_key import ApiKey


def _hash_api_key_value(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def create_api_key(
    db: Session,
    *,
    user_id: str,
    name: str | None = None,
    expires_at: datetime | None = None,
) -> tuple[ApiKey, str]:
    raw_key = f"sk_socialeval_{secrets.token_urlsafe(32)}"
    hashed_key = _hash_api_key_value(raw_key)
    api_key = ApiKey(
        user_id=user_id,
        name=name,
        key_prefix=raw_key[:20],
        key_hash=hashed_key,
        expires_at=expires_at,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key, raw_key


def verify_api_key(db: Session, raw_key: str) -> ApiKey | None:
    hashed_key = _hash_api_key_value(raw_key)
    api_key = db.query(ApiKey).filter(ApiKey.key_hash == hashed_key).first()
    if api_key is None or not api_key.is_active:
        return None
    if api_key.expires_at is not None and api_key.expires_at <= utc_now():
        return None
    if not hmac.compare_digest(api_key.key_hash, hashed_key):
        return None
    api_key.last_used_at = utc_now()
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    return api_key
