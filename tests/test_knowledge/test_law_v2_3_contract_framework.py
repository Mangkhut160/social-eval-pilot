from pathlib import Path

import yaml


FRAMEWORK_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "frameworks"
    / "law-v2.4-20260422.yaml"
)


def load_framework() -> dict:
    return yaml.safe_load(FRAMEWORK_PATH.read_text(encoding="utf-8"))


def test_v2_4_framework_file_exists() -> None:
    assert FRAMEWORK_PATH.exists()


def test_v2_4_has_output_contract_and_decision_order() -> None:
    framework = load_framework()

    assert "output_contract" in framework
    assert "decision_order" in framework
    assert framework["decision_order"]["steps"] == [
        "定位评价对象",
        "抽取关键证据",
        "判断是否触发上限规则",
        "确定分档",
        "给出最终分数",
        "输出摘要与评分理由",
    ]


def test_v2_4_output_contract_requires_comparable_fields() -> None:
    framework = load_framework()
    required_fields = framework["output_contract"]["required_fields"]

    assert required_fields == [
        "dimension",
        "score",
        "band",
        "summary",
        "core_judgment",
        "score_rationale",
        "evidence_quotes",
        "strengths",
        "weaknesses",
        "limit_rule_triggered",
        "boundary_note",
        "review_flags",
    ]


def test_v2_4_dimensions_define_rule_ids_and_prompt_contract_fields() -> None:
    framework = load_framework()

    for dimension in framework["dimensions"]:
        rule_ids = [rule.get("rule_id") for rule in dimension["ceiling_rules"]]
        assert all(rule_ids), f"{dimension['key']} 缺少 rule_id"

        prompt = dimension["prompt_template"]
        assert '"band"' in prompt
        assert '"summary"' in prompt
        assert '"core_judgment"' in prompt
        assert '"score_rationale"' in prompt
        assert '"rule_id"' in prompt


def test_v2_4_prompts_forbid_missing_score_and_invalid_review_flags() -> None:
    framework = load_framework()
    guardrails = framework["output_contract"]["guardrails"]

    assert "score 缺失视为失败输出" in guardrails
    assert 'review_flags 无触发时返回 ["none"]' in guardrails
    assert "不得同时返回 none 和其他 review flag" in guardrails
