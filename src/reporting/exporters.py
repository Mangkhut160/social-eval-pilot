from __future__ import annotations

import json
from html import escape

import fitz
from sqlalchemy.orm import Session

from src.core.object_storage import StorageBackend, get_storage_backend
from src.models.report import Report, ReportExport


def _format_report_type(report_type: str) -> str:
    return {"public": "公开报告", "internal": "内部报告"}.get(report_type, report_type)


def _format_score(value: object, *, suffix: str = "") -> str:
    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".") + suffix
    except (TypeError, ValueError):
        return f"待生成{suffix}" if suffix else "待生成"


def _normalize_text_items(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            items.extend(_normalize_text_items(item))
        return items
    text = str(value).strip()
    return [text] if text else []


def _build_list_html(items: list[str], *, class_name: str = "text-list") -> str:
    if not items:
        return '<p class="muted">暂无内容。</p>'
    rendered = "".join(f"<li>{escape(item)}</li>" for item in items)
    return f'<ul class="{class_name}">{rendered}</ul>'


def _build_ai_summary_html(report: Report) -> str:
    report_data = report.report_data
    if report_data.get("precheck_status") == "reject":
        issues = _normalize_text_items(report_data.get("precheck_result", {}).get("issues"))
        recommendation = report_data.get("precheck_result", {}).get("recommendation")
        sections = [
            '<section class="section">',
            "<h2>预检结果</h2>",
            '<p class="lead">该稿件在预检阶段被拒稿，未进入正式维度评分。</p>',
            "<h3>发现的问题</h3>",
            _build_list_html(issues),
        ]
        if recommendation:
            sections.append(f'<p class="note">建议：{escape(str(recommendation))}</p>')
        sections.append("</section>")
        return "".join(sections)

    dimensions = report_data.get("dimensions", [])
    analysis_items: list[str] = []
    evidence_items: list[str] = []
    high_confidence_count = 0
    dimension_name_by_key: dict[str, str] = {}

    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        dimension_name = str(dimension.get("name_zh", "")).strip() or str(
            dimension.get("name_en", "")
        ).strip()
        if not dimension_name:
            continue
        dimension_name_by_key[str(dimension.get("key", dimension_name))] = dimension_name
        ai_payload = dimension.get("ai", {})
        if isinstance(ai_payload, dict) and ai_payload.get("is_high_confidence"):
            high_confidence_count += 1
        for analysis in _normalize_text_items(
            ai_payload.get("analysis") if isinstance(ai_payload, dict) else None
        ):
            analysis_items.append(f"{dimension_name}：{analysis}")
        for quote in _normalize_text_items(
            ai_payload.get("evidence_quotes") if isinstance(ai_payload, dict) else None
        ):
            evidence_items.append(f"{dimension_name}：{quote}")

    low_confidence_count = max(len(dimensions) - high_confidence_count, 0)
    summary_cards = f"""
    <div class="summary-grid">
      <div class="summary-card">
        <span>综合得分</span>
        <strong>{escape(_format_score(report_data.get("weighted_total"), suffix="/100"))}</strong>
      </div>
      <div class="summary-card">
        <span>高置信度维度</span>
        <strong>{high_confidence_count}</strong>
      </div>
      <div class="summary-card">
        <span>需复核维度</span>
        <strong>{low_confidence_count}</strong>
      </div>
      <div class="summary-card">
        <span>AI 结论条目</span>
        <strong>{len(analysis_items)}</strong>
      </div>
    </div>
    """

    dimension_sections = []
    for dimension in dimensions:
        if not isinstance(dimension, dict):
            continue
        ai_payload = dimension.get("ai", {})
        if not isinstance(ai_payload, dict):
            continue
        dimension_name = str(dimension.get("name_zh", "")).strip() or str(
            dimension.get("name_en", "")
        ).strip()
        confidence_label = "高置信度" if ai_payload.get("is_high_confidence") else "需要复核"
        analyses = _normalize_text_items(ai_payload.get("analysis"))
        evidence_quotes = _normalize_text_items(ai_payload.get("evidence_quotes"))
        dimension_sections.append(
            f"""
            <section class="dimension-card">
              <h3>{escape(dimension_name)}</h3>
              <p class="metric-line">
                <span>AI 均分：{escape(_format_score(ai_payload.get("mean_score")))}</span>
                <span>标准差：{escape(_format_score(ai_payload.get("std_score")))}</span>
                <span>状态：{confidence_label}</span>
              </p>
              <h4>AI 分析</h4>
              {_build_list_html(analyses)}
              <h4>证据摘录</h4>
              {_build_list_html(evidence_quotes)}
            </section>
            """
        )

    expert_sections: list[str] = []
    expert_reviews = report_data.get("expert_reviews", [])
    for review in expert_reviews if isinstance(expert_reviews, list) else []:
        if not isinstance(review, dict):
            continue
        comments = review.get("comments", [])
        if not isinstance(comments, list) or not comments:
            continue
        rendered_comments = []
        for comment in comments:
            if not isinstance(comment, dict):
                continue
            dimension_name = dimension_name_by_key.get(
                str(comment.get("dimension_key", "")),
                str(comment.get("dimension_key", "")),
            )
            rendered_comments.append(
                f"""
                <li>
                  <strong>{escape(dimension_name)}</strong>
                  <span>专家评分：{escape(_format_score(comment.get("expert_score")))}</span>
                  <p>{escape(str(comment.get("reason", "")))}</p>
                </li>
                """
            )
        if rendered_comments:
            expert_sections.append(
                f"""
                <section class="section">
                  <h3>复核提交 {escape(str(review.get("review_id", "")))}</h3>
                  <ul class="expert-list">
                    {''.join(rendered_comments)}
                  </ul>
                </section>
                """
            )

    expert_html = (
        f'<section class="section"><h2>专家复核意见</h2>{"".join(expert_sections)}</section>'
        if expert_sections
        else ""
    )

    return (
        '<section class="section">'
        "<h2>AI评价摘要</h2>"
        '<p class="lead">以下内容为系统基于当前报告直接整理出的 AI 评价结论与关键输出。</p>'
        f"{summary_cards}"
        '<section class="section"><h3>AI 主要结论</h3>'
        f"{_build_list_html(analysis_items)}"
        "</section>"
        '<section class="section"><h3>AI 关键输出</h3>'
        f"{_build_list_html(evidence_items)}"
        "</section>"
        f"{''.join(dimension_sections)}"
        f"{expert_html}"
        "</section>"
    )


def _build_report_html(report: Report) -> str:
    report_data = report.report_data
    evaluation_config = report_data.get("evaluation_config") or {}
    selected_models = evaluation_config.get("selected_models", [])
    model_text = "、".join(str(model) for model in selected_models) if selected_models else "待生成"
    rounds = evaluation_config.get("evaluation_rounds")
    paper_title = report_data.get("paper_title") or report.paper_id
    meta_items = [
        ("报告类型", _format_report_type(report.report_type)),
        ("稿件标题", str(paper_title)),
        ("报告版本", str(report.version)),
        ("综合得分", _format_score(report_data.get("weighted_total"), suffix="/100")),
        ("评测轮数", _format_score(rounds, suffix=" 轮") if rounds is not None else "待生成"),
        ("评测模型", model_text),
    ]
    meta_cards = "".join(
        f"""
          <div class="meta-card">
            <p class="meta-line"><strong>{escape(label)}：</strong>{escape(value)}</p>
          </div>
        """
        for label, value in meta_items
    )

    return f"""
    <!doctype html>
    <html lang="zh-CN">
      <head>
        <meta charset="utf-8" />
        <style>
          @page {{
            size: A4;
            margin: 20mm 16mm;
          }}
          body {{
            font-family: "Noto Sans CJK SC", "WenQuanYi Zen Hei", "Source Han Sans SC", sans-serif;
            color: #1f2430;
            font-size: 12px;
            line-height: 1.65;
          }}
          h1, h2, h3, h4, p {{
            margin: 0 0 8px;
          }}
          h1 {{
            font-size: 22px;
            margin-bottom: 12px;
          }}
          h2 {{
            font-size: 16px;
            margin-top: 18px;
          }}
          h3 {{
            font-size: 14px;
            margin-top: 14px;
          }}
          h4 {{
            font-size: 12px;
            margin-top: 10px;
          }}
          .meta-grid,
          .summary-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 10px;
            margin: 12px 0;
          }}
          .meta-card,
          .summary-card,
          .dimension-card,
          .section {{
            border: 1px solid #d7dde8;
            border-radius: 10px;
            padding: 10px 12px;
            background: #fbfcfe;
          }}
          .meta-card span,
          .summary-card span,
          .muted {{
            color: #5f6777;
          }}
          .summary-card strong {{
            display: block;
            margin-top: 4px;
            font-size: 14px;
          }}
          .meta-line {{
            margin: 0;
            color: #334155;
          }}
          .meta-line strong,
          .summary-card strong {{
            font-size: 14px;
          }}
          .lead,
          .note {{
            color: #334155;
          }}
          .metric-line {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            color: #5f6777;
          }}
          ul {{
            margin: 0;
            padding-left: 18px;
          }}
          li {{
            margin-bottom: 6px;
          }}
          .expert-list {{
            list-style: none;
            padding-left: 0;
          }}
          .expert-list li {{
            border-top: 1px solid #e5e7eb;
            padding-top: 8px;
            margin-top: 8px;
          }}
          .expert-list li:first-child {{
            border-top: none;
            padding-top: 0;
            margin-top: 0;
          }}
        </style>
      </head>
      <body>
        <h1>文科论文评价系统报告</h1>
        <div class="meta-grid">
          {meta_cards}
        </div>
        {_build_ai_summary_html(report)}
      </body>
    </html>
    """


def export_report_json(report: Report) -> bytes:
    return json.dumps(report.report_data, ensure_ascii=False, indent=2).encode("utf-8")


def _estimate_page_height(report: Report) -> int:
    report_data = report.report_data
    dimensions = report_data.get("dimensions", [])
    dimension_count = len(dimensions) if isinstance(dimensions, list) else 0
    analysis_count = 0
    evidence_count = 0
    expert_comment_count = 0

    if isinstance(dimensions, list):
        for dimension in dimensions:
            if not isinstance(dimension, dict):
                continue
            ai_payload = dimension.get("ai", {})
            if not isinstance(ai_payload, dict):
                continue
            analysis_count += len(_normalize_text_items(ai_payload.get("analysis")))
            evidence_count += len(_normalize_text_items(ai_payload.get("evidence_quotes")))

    expert_reviews = report_data.get("expert_reviews", [])
    if isinstance(expert_reviews, list):
        for review in expert_reviews:
            if isinstance(review, dict) and isinstance(review.get("comments"), list):
                expert_comment_count += len(review["comments"])

    estimated = (
        900
        + dimension_count * 180
        + analysis_count * 42
        + evidence_count * 36
        + expert_comment_count * 70
    )
    return max(estimated, 900)


def export_report_pdf(report: Report) -> bytes:
    html = _build_report_html(report)
    page_width = 595
    page_height = _estimate_page_height(report)
    document: fitz.Document | None = None

    try:
        for attempt in range(5):
            candidate = fitz.open()
            page = candidate.new_page(width=page_width, height=page_height)
            _, scale = page.insert_htmlbox(
                fitz.Rect(36, 36, page_width - 36, page_height - 36),
                html,
            )
            if scale >= 0.98 or attempt == 4:
                document = candidate
                break
            candidate.close()
            page_height = int(page_height * 1.35)

        if document is None:
            raise RuntimeError("Failed to render report PDF")
        return document.tobytes()
    finally:
        if document is not None:
            document.close()


def persist_report_export(
    db: Session,
    *,
    report: Report,
    export_type: str,
    content: bytes,
    storage_backend: StorageBackend | None = None,
) -> ReportExport:
    suffix = "json" if export_type == "json" else "pdf"
    key = f"exports/{report.id}-{report.version}-{report.report_type}.{suffix}"
    stored = (storage_backend or get_storage_backend()).put_bytes(
        key=key,
        content=content,
        content_type="application/json" if export_type == "json" else "application/pdf",
    )
    export = ReportExport(
        report_id=report.id,
        export_type=export_type,
        file_path=stored.location,
    )
    db.add(export)
    db.commit()
    db.refresh(export)
    return export
