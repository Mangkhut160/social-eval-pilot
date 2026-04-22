import pytest
from src.ingestion.reference_extractor import extract_references
from src.ingestion.structure_detector import detect_structure


# 参考文献提取测试

def test_extract_references_chinese():
    text = "论文正文内容...\n\n参考文献\n[1] 张三，法律研究，2020\n[2] 李四，法学理论，2021"
    body, refs = extract_references(text)
    assert len(refs) == 2
    assert "张三" in refs[0]
    assert "法律研究" not in body


def test_no_references_returns_full_text():
    text = "只有正文，没有参考文献。"
    body, refs = extract_references(text)
    assert body == text
    assert refs == []


def test_extract_english_references():
    text = "Main content here.\n\nReferences\n[1] Smith, J. (2020). Law Review.\n[2] Jones, A. (2021). Legal Theory."
    body, refs = extract_references(text)
    assert len(refs) == 2
    assert "Smith" in refs[0]
    assert "Main content" in body


# 结构检测测试

def test_detect_structure_degraded_when_no_headings():
    text = "这是一段没有章节标题的纯文本。" * 10
    paper = detect_structure(text)
    assert paper.structure_status == "degraded"
    assert paper.body == text
    assert len(paper.warnings) > 0


def test_detect_structure_detected_with_chinese_headings():
    text = """摘要
这是摘要内容。

一、引言
这是引言内容。

二、主体内容
主要论证部分。

三、结论
结论文字。"""
    paper = detect_structure(text)
    assert paper.structure_status == "detected"


def test_processed_paper_has_required_fields():
    from src.ingestion.schemas import ProcessedPaper
    paper = ProcessedPaper(full_text="test", structure_status="degraded")
    assert paper.references == []
    assert paper.warnings == []
    assert paper.abstract == ""
