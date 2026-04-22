from __future__ import annotations

from pydantic import BaseModel


class ReportHistoryItemResponse(BaseModel):
    report_id: str
    report_type: str
    version: int
    is_current: bool
    weighted_total: float
    precheck_status: str | None = None
    created_at: str
    available_export_formats: list[str]


class ReportHistoryResponse(BaseModel):
    items: list[ReportHistoryItemResponse]
