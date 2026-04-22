from __future__ import annotations

from src.ingestion.schemas import ProcessedPaper
from src.knowledge.schemas import Dimension, Framework


def _paper_content(paper: ProcessedPaper) -> str:
    return paper.body or paper.full_text


def _reference_content(paper: ProcessedPaper) -> str:
    if not paper.references:
        return "（无）"
    return "\n".join(paper.references)


def _append_context(template: str, paper: ProcessedPaper) -> str:
    return (
        f"{template.rstrip()}\n\n"
        f"论文正文：\n{_paper_content(paper)}\n"
        f"---\n"
        f"参考文献列表：\n{_reference_content(paper)}"
    )


def _render_template(template: str, paper: ProcessedPaper) -> str:
    if "{paper_content}" in template or "{references}" in template:
        return template.format(
            paper_content=_paper_content(paper),
            references=_reference_content(paper),
        )
    return _append_context(template, paper)


def build_prompt(dimension: Dimension, paper: ProcessedPaper) -> str:
    return _render_template(dimension.prompt_template, paper)


def build_precheck_prompt(framework: Framework, paper: ProcessedPaper) -> str:
    if framework.precheck is None:
        raise ValueError("当前框架未配置 precheck")
    return _render_template(framework.precheck.prompt_template, paper)
