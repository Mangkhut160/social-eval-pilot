from src.evaluation.prompt_builder import build_precheck_prompt, build_prompt
from src.ingestion.schemas import ProcessedPaper
from src.knowledge.loader import load_framework


def test_law_framework_prompts_are_actionable_and_renderable():
    framework = load_framework("configs/frameworks/law_v1.yaml")
    paper = ProcessedPaper(
        full_text="论文全文",
        body="论文正文",
        references=["参考文献一", "参考文献二"],
        structure_status="detected",
    )

    required_markers = [
        "不得直接凭整体印象",
        "证据片段",
        "缺陷触发",
        "跨维度边界",
        "分档锚点",
        "请严格按以下 JSON 格式返回",
    ]

    for dimension in framework.dimensions:
        prompt = build_prompt(dimension, paper)
        assert "论文正文" in prompt
        assert "参考文献一" in prompt
        assert f'"dimension": "{dimension.key}"' in prompt
        for marker in required_markers:
            assert marker in prompt


def test_law_v2_prompt_builder_appends_paper_context_without_placeholders():
    framework = load_framework("configs/frameworks/law-v2.0-20260413.yaml")
    paper = ProcessedPaper(
        full_text="论文全文",
        body="这是一段法学论文正文",
        references=["参考文献A", "参考文献B"],
        structure_status="detected",
    )

    dimension = framework.dimensions[0]
    prompt = build_prompt(dimension, paper)

    assert "这是一段法学论文正文" in prompt
    assert "参考文献A" in prompt
    assert '{"dimension": "problem_originality"' in prompt
    assert "论文正文：" in prompt
    assert "参考文献列表：" in prompt


def test_law_v2_precheck_prompt_builder_appends_paper_context():
    framework = load_framework("configs/frameworks/law-v2.0-20260413.yaml")
    paper = ProcessedPaper(
        full_text="完整论文内容",
        body="正文片段",
        references=[],
        structure_status="detected",
    )

    prompt = build_precheck_prompt(framework, paper)

    assert "学术规范性准入检查" in prompt
    assert "正文片段" in prompt
    assert '{"status": "pass|reject"' in prompt


def test_law_v2_precheck_prompt_relaxes_format_requirements_and_rejects_non_humanities():
    framework = load_framework("configs/frameworks/law-v2.0-20260413.yaml")
    paper = ProcessedPaper(
        full_text="完整论文内容",
        body="正文片段",
        references=[],
        structure_status="detected",
    )

    prompt = build_precheck_prompt(framework, paper)

    assert "不要因为参考文献格式、脚注样式、图表编号等细节不够标准就直接退稿" in prompt
    assert "如果论文主题明显属于理工农医等非文科领域，应直接判定为 reject" in prompt
