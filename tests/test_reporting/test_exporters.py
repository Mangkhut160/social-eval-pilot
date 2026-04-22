from __future__ import annotations

import warnings
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

import src.models  # noqa: F401
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.core.object_storage import LocalStorageBackend, StoredObject
from src.core.database import Base
from src.models.report import Report
from src.reporting import exporters


class FakeRemoteStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_bytes(
        self,
        *,
        key: str,
        content: bytes,
        content_type: str | None = None,
    ) -> StoredObject:
        location = f"s3://socialeval-test/{key}"
        self.objects[location] = content
        return StoredObject(location=location, key=key)

    def get_bytes(self, location: str) -> bytes:
        return self.objects[location]


@contextmanager
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = testing_session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def build_report(db: Session) -> Report:
    report = Report(
        task_id="task-1",
        paper_id="paper-1",
        version=1,
        report_type="internal",
        is_current=True,
        weighted_total=88.5,
        report_data={"weighted_total": 88.5, "dimensions": []},
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def test_persist_report_export_writes_to_local_storage(tmp_path: Path) -> None:
    with db_session(tmp_path) as db:
        report = build_report(db)
        storage_backend = LocalStorageBackend(tmp_path)

        exporters.persist_report_export(
            db,
            report=report,
            export_type="json",
            content=b'{"ok": true}',
            storage_backend=storage_backend,
        )

        export = db.query(src.models.report.ReportExport).one()
        assert Path(export.file_path).exists()
        assert Path(export.file_path).read_bytes() == b'{"ok": true}'


def test_persist_report_export_writes_to_remote_storage(tmp_path: Path) -> None:
    with db_session(tmp_path) as db:
        report = build_report(db)
        storage_backend = FakeRemoteStorage()

        exporters.persist_report_export(
            db,
            report=report,
            export_type="pdf",
            content=b"%PDF-1.7",
            storage_backend=storage_backend,
        )

        export = db.query(src.models.report.ReportExport).one()
        assert export.file_path == f"s3://socialeval-test/exports/{report.id}-1-internal.pdf"
        assert storage_backend.get_bytes(export.file_path) == b"%PDF-1.7"


def test_export_report_pdf_emits_no_missing_glyph_warnings_for_chinese_title(tmp_path: Path) -> None:
    with db_session(tmp_path) as db:
        report = build_report(db)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            content = exporters.export_report_pdf(report)

        assert content.startswith(b"%PDF")
        missing_glyph_warnings = [
            item
            for item in caught
            if "missing from font" in str(item.message)
        ]
        assert missing_glyph_warnings == []
