from sqlalchemy.orm import Session
from src.models.framework import FrameworkVersion


def save_framework_version(db: Session, yaml_content: str, framework_name: str) -> FrameworkVersion:
    version = FrameworkVersion(framework_name=framework_name, yaml_content=yaml_content)
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def rollback_to_version(db: Session, version_id: str) -> str:
    version = db.get(FrameworkVersion, version_id)
    if not version:
        raise ValueError("版本不存在")
    return version.yaml_content


def list_versions(db: Session, framework_name: str) -> list[FrameworkVersion]:
    return db.query(FrameworkVersion).filter_by(framework_name=framework_name).order_by(FrameworkVersion.created_at.desc()).all()
