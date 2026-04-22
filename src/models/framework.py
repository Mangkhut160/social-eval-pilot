import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from src.core.database import Base
from src.core.time import utc_now


class FrameworkVersion(Base):
    __tablename__ = "framework_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    framework_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version_tag: Mapped[str | None] = mapped_column(String(50), nullable=True)
    yaml_content: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[str] = mapped_column(String(1), default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
