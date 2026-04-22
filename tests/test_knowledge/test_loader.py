from pathlib import Path

import jsonschema
import pytest
import yaml

from src.core.exceptions import KnowledgeError
from src.knowledge.loader import (
    SCHEMA_V3_PATH,
    _schema_path_for_data,
    load_framework,
    load_framework_from_string,
)


FRAMEWORK_DIR = Path(__file__).resolve().parents[2] / "configs" / "frameworks"


def test_load_legacy_law_framework_succeeds():
    fw = load_framework("configs/frameworks/law_v1.yaml")
    assert fw.discipline == "law"
    assert len(fw.dimensions) == 6
    assert fw.name == "法学论文评价框架"
    assert fw.std_threshold == 5.0
    # 验证权重之和约为 1.0
    total_weight = sum(d.weight for d in fw.dimensions)
    assert abs(total_weight - 1.0) < 0.01


def test_load_law_framework_dimensions_have_prompts():
    fw = load_framework("configs/frameworks/law_v1.yaml")
    for dim in fw.dimensions:
        assert dim.prompt_template.strip() != ""
        assert "{paper_content}" in dim.prompt_template
        assert "{references}" in dim.prompt_template


def test_load_law_v2_framework_succeeds():
    fw = load_framework("configs/frameworks/law-v2.0-20260413.yaml")
    assert fw.name == "法学评价框架 v2.0"
    assert fw.discipline == "法学"
    assert fw.version == "2.0.0"
    assert fw.std_threshold == 5.0
    assert len(fw.dimensions) == 6
    assert fw.precheck is not None
    assert fw.precheck.name == "学术规范性准入检查"
    assert fw.scoring_structure is not None
    assert fw.scoring_structure.total_max == 100


def test_load_law_v2_framework_preserves_new_dimension_names():
    fw = load_framework("configs/frameworks/law-v2.0-20260413.yaml")
    dimension_keys = [dim.key for dim in fw.dimensions]
    assert "analytical_framework" in dimension_keys
    assert "conclusion_consensus" in dimension_keys
    assert "theoretical_construction" not in dimension_keys
    assert "scholarly_consensus" not in dimension_keys


def test_load_law_v23_framework_succeeds_and_normalizes_runtime_fields():
    fw = load_framework("configs/frameworks/law-v2.3-20260421.yaml")
    assert fw.name == "法学评价框架 v2.3（研究版）"
    assert fw.discipline == "法学"
    assert fw.version == "2.3.0"
    assert fw.std_threshold == 5.0
    assert len(fw.dimensions) == 6
    assert fw.scoring_structure is not None
    assert fw.scoring_structure.total_max == 100
    assert fw.discrimination_threshold is not None
    assert fw.discrimination_threshold.levels[0].threshold == 50
    assert fw.expert_review_triggers is not None
    assert (
        fw.expert_review_triggers.dimension_triggers[0].dimension
        == "problem_originality"
    )
    assert fw.anchors is not None
    assert fw.anchors.positive[0].paper == "林来梵《民法典编纂的宪法学透析》"
    assert fw.anchors.positive[0].source == "法学研究 2016年第4期"
    assert fw.anchors.negative[0].reason == "追热点式选题，问题虚构"
    assert (
        fw.raw_config["governance_appendix"]["discrimination_threshold"]["levels"][0][
            "threshold"
        ]
        == 50
    )
    assert fw.raw_config["governance_appendix"]["sample_anchors"]["positive"][0]["type"]
    assert fw.raw_config["enums"]["review_flags"]["common"]
    assert fw.raw_config["output_constraints"]["dimension_max_chars"] == 500


def test_v3_shaped_framework_routes_to_schema_v3():
    data = yaml.safe_load(
        (FRAMEWORK_DIR / "law-v2.3-20260421.yaml").read_text(encoding="utf-8")
    )

    assert _schema_path_for_data(data) == SCHEMA_V3_PATH


@pytest.mark.parametrize("signal_key", ["enums", "output_constraints"])
def test_v3_secondary_structural_signal_routes_to_schema_v3(signal_key):
    data = yaml.safe_load(
        (FRAMEWORK_DIR / "law-v2.3-20260421.yaml").read_text(encoding="utf-8")
    )
    data.pop("governance_appendix")

    for candidate in ("enums", "output_constraints"):
        if candidate != signal_key:
            data.pop(candidate, None)

    assert _schema_path_for_data(data) == SCHEMA_V3_PATH


def test_invalid_v3_framework_is_rejected():
    data = yaml.safe_load(
        (FRAMEWORK_DIR / "law-v2.3-20260421.yaml").read_text(encoding="utf-8")
    )
    data.pop("governance_appendix")

    assert _schema_path_for_data(data) == SCHEMA_V3_PATH

    with pytest.raises(jsonschema.ValidationError, match="governance_appendix"):
        load_framework_from_string(yaml.safe_dump(data, allow_unicode=True, sort_keys=False))


def test_weight_sum_must_be_one(tmp_path):
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("""
name: test
discipline: test
version: "1.0"
std_threshold: 5.0
dimensions:
  - key: d1
    name_zh: D1
    name_en: D1
    weight: 0.5
    prompt_template: "{paper_content} {references}"
  - key: d2
    name_zh: D2
    name_en: D2
    weight: 0.6
    prompt_template: "{paper_content} {references}"
""")
    with pytest.raises(KnowledgeError, match="权重之和"):
        load_framework(bad_yaml)


def test_missing_required_field_raises_validation_error(tmp_path):
    bad_yaml = tmp_path / "bad2.yaml"
    bad_yaml.write_text("""
name: test
discipline: test
dimensions: []
""")
    with pytest.raises(jsonschema.ValidationError, match="version"):
        load_framework(bad_yaml)
