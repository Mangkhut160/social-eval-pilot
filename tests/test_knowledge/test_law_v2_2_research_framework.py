from textwrap import dedent

import yaml

from src.knowledge.loader import (
    SCHEMA_V3_PATH,
    _schema_path_for_data,
    load_framework,
    load_framework_from_string,
)


_MINIMAL_DIMENSIONS = [
    {
        "key": "problem_originality",
        "name_zh": "问题创新性",
        "name_en": "Problem Originality",
        "weight": 0.30,
        "position": 1,
        "position_name": "起点",
        "description": "研究问题是否具有创新性与枢纽意义。",
        "evaluate": ["是否提出真问题"],
        "do_not_evaluate": ["不评价语言修辞"],
        "ceiling_rules": [
            {"trigger": "问题意识不足", "score_ceiling": 60, "priority": 1}
        ],
        "scoring_criteria": {
            "excellent": {"range": [27, 30], "indicators": ["问题具有枢纽意义"]},
            "good": {"range": [21, 26], "indicators": ["问题明确且有学术价值"]},
            "marginal": {"range": [15, 20], "indicators": ["问题存在但价值有限"]},
            "unacceptable": {"range": [0, 14], "indicators": ["问题意识缺失"]},
        },
        "prompt_template": "请依据{paper_content}和{references}评估问题创新性。",
    },
    {
        "key": "literature_insight",
        "name_zh": "现状洞察度",
        "name_en": "Literature Insight",
        "weight": 0.15,
        "position": 2,
        "position_name": "定位",
        "description": "对既有研究的把握与识别未竟问题的能力。",
        "evaluate": ["是否识别研究缺口"],
        "do_not_evaluate": ["不评价引文数量本身"],
        "ceiling_rules": [
            {"trigger": "文献综述停留于罗列", "score_ceiling": 65, "priority": 1}
        ],
        "scoring_criteria": {
            "excellent": {"range": [14, 15], "indicators": ["能够精确定位未竟点"]},
            "good": {"range": [11, 13], "indicators": ["对研究现状把握较完整"]},
            "marginal": {"range": [8, 10], "indicators": ["有一定综述但洞察有限"]},
            "unacceptable": {"range": [0, 7], "indicators": ["缺乏文献对话"]},
        },
        "prompt_template": "请依据{paper_content}和{references}评估现状洞察度。",
    },
    {
        "key": "analytical_framework",
        "name_zh": "分析框架建构力",
        "name_en": "Analytical Framework Construction",
        "weight": 0.15,
        "position": 3,
        "position_name": "工具",
        "description": "是否建立可操作的分析框架。",
        "evaluate": ["是否形成清晰框架"],
        "do_not_evaluate": ["不评价排版格式"],
        "ceiling_rules": [
            {"trigger": "缺乏明确分析框架", "score_ceiling": 60, "priority": 1}
        ],
        "scoring_criteria": {
            "excellent": {"range": [14, 15], "indicators": ["框架完整且可操作"]},
            "good": {"range": [11, 13], "indicators": ["框架较完整"]},
            "marginal": {"range": [8, 10], "indicators": ["框架初步成形"]},
            "unacceptable": {"range": [0, 7], "indicators": ["缺乏分析框架"]},
        },
        "prompt_template": "请依据{paper_content}和{references}评估分析框架建构力。",
    },
    {
        "key": "logical_coherence",
        "name_zh": "逻辑严密性",
        "name_en": "Logical Coherence",
        "weight": 0.25,
        "position": 4,
        "position_name": "骨架",
        "description": "论证链条是否严密。",
        "evaluate": ["推理是否层层递进"],
        "do_not_evaluate": ["不评价结论立场本身"],
        "ceiling_rules": [
            {"trigger": "存在明显逻辑跳跃", "score_ceiling": 55, "priority": 1}
        ],
        "scoring_criteria": {
            "excellent": {"range": [23, 25], "indicators": ["论证链条严密且不可颠倒"]},
            "good": {"range": [18, 22], "indicators": ["论证较为完整"]},
            "marginal": {"range": [13, 17], "indicators": ["论证存在跳跃"]},
            "unacceptable": {"range": [0, 12], "indicators": ["论证严重失衡"]},
        },
        "prompt_template": "请依据{paper_content}和{references}评估逻辑严密性。",
    },
    {
        "key": "conclusion_acceptability",
        "name_zh": "结论可接受性",
        "name_en": "Conclusion Acceptability",
        "weight": 0.10,
        "position": 5,
        "position_name": "落脚",
        "description": "结论在制度框架内是否可接受。",
        "evaluate": ["结论是否具有制度可行性"],
        "do_not_evaluate": ["不评价政策偏好"],
        "ceiling_rules": [
            {"trigger": "结论缺乏制度可行性", "score_ceiling": 60, "priority": 1}
        ],
        "scoring_criteria": {
            "excellent": {"range": [9, 10], "indicators": ["结论兼具创新性与可行性"]},
            "good": {"range": [7, 8], "indicators": ["结论基本可接受"]},
            "marginal": {"range": [5, 6], "indicators": ["结论可行性存疑"]},
            "unacceptable": {"range": [0, 4], "indicators": ["结论不可接受"]},
        },
        "prompt_template": "请依据{paper_content}和{references}评估结论可接受性。",
    },
    {
        "key": "forward_extension",
        "name_zh": "前瞻延展性",
        "name_en": "Forward Extension",
        "weight": 0.05,
        "position": 6,
        "position_name": "开放",
        "description": "是否为后续研究提供拓展方向。",
        "evaluate": ["是否提出后续研究地图"],
        "do_not_evaluate": ["不评价文风"],
        "ceiling_rules": [
            {"trigger": "未提供后续研究空间", "score_ceiling": 50, "priority": 1}
        ],
        "scoring_criteria": {
            "excellent": {"range": [5, 5], "indicators": ["明确打开后续研究空间"]},
            "good": {"range": [4, 4], "indicators": ["提出有价值的延展方向"]},
            "marginal": {"range": [2, 3], "indicators": ["仅有笼统展望"]},
            "unacceptable": {"range": [0, 1], "indicators": ["缺乏延展意识"]},
        },
        "prompt_template": "请依据{paper_content}和{references}评估前瞻延展性。",
    },
]


_DEF_BASE = {
    "metadata": {
        "name": "法学评价框架 v2.2（研究版）",
        "version": "2.2.0",
        "discipline": "法学",
        "source": "研究版显式结构样例",
        "created": "2026-04-21",
        "status": "research",
    },
    "precheck": {
        "name": "学术规范性准入检查",
        "description": "进入六维评分前的前置筛选。",
        "criteria": [
            {
                "key": "writing_norms",
                "name_zh": "写作规范性",
                "description": "语言表达清晰、结构完整。",
                "pass_required": True,
            }
        ],
        "prompt_template": "请基于{paper_content}检查写作规范性。",
    },
    "scoring_structure": {
        "total_max": 100,
        "description": "六维度评分，总分100分。",
    },
    "dimensions": _MINIMAL_DIMENSIONS,
    "evaluation_chain": {
        "description": "起点→定位→工具→骨架→落脚→开放。",
        "sequence": [
            {"dimension": dimension["key"], "reason": f"按{dimension['name_zh']}顺序判断。"}
            for dimension in _MINIMAL_DIMENSIONS
        ],
    },
    "enums": {
        "review_flags": {
            "common": [
                {
                    "key": "manual_review",
                    "name_zh": "人工复核",
                    "description": "存在需要人工复核的信号。",
                    "action": "route_to_expert",
                }
            ]
        }
    },
    "output_constraints": {"dimension_max_chars": 500},
    "governance_appendix": {
        "note": "治理附录仅用于研究校准与系统治理。",
        "discrimination_threshold": {
            "description": "区分度阈值。",
            "levels": [
                {"level": "high", "threshold": 50, "action": "进入高区分样本"}
            ],
        },
        "expert_review_triggers": {
            "dimension_triggers": [
                {
                    "dimension": "logical_coherence",
                    "condition": "存在明显逻辑跳跃",
                }
            ],
            "overall_triggers": [
                {"condition": "多模型分歧过大", "action": "进入专家复核"}
            ],
        },
        "validation_plan": {
            "description": "研究版校准计划。",
            "steps": ["对比人工评分结果"],
        },
        "reliability_verification": {
            "multi_model_consensus": {
                "recommended_models": 3,
                "max_models": 5,
                "thresholds": {"high_confidence": "std <= 5"},
            },
            "system_risks": [],
        },
        "sample_anchors": {
            "note": "样本锚点用于校准和验证，不直接进入评分prompt。",
            "positive": [
                {
                    "paper": "林来梵《民法典编纂的宪法学透析》",
                    "type": "理论型",
                    "source": "法学研究 2016年第4期",
                }
            ],
            "negative": [
                {
                    "paper": "《论新质生产力区域协调发展的法治化之道》",
                    "type": "追热点型",
                    "reason": "追热点式选题，问题虚构",
                }
            ],
        },
    },
}


V22_STYLE_RESEARCH_YAML = dedent(
    yaml.safe_dump(_DEF_BASE, allow_unicode=True, sort_keys=False)
)


def test_v22_style_research_framework_routes_to_schema_v3_based_on_structure():
    data = yaml.safe_load(V22_STYLE_RESEARCH_YAML)

    assert _schema_path_for_data(data) == SCHEMA_V3_PATH


def test_v22_style_research_framework_loads_from_file_and_string_and_normalizes_runtime_fields(
    tmp_path,
):
    yaml_path = tmp_path / "law-v2.2-research.yaml"
    yaml_path.write_text(V22_STYLE_RESEARCH_YAML, encoding="utf-8")

    frameworks = [
        load_framework(yaml_path),
        load_framework_from_string(V22_STYLE_RESEARCH_YAML),
    ]

    for framework in frameworks:
        assert framework.version == "2.2.0"
        assert framework.discrimination_threshold is not None
        assert framework.discrimination_threshold.levels[0].threshold == 50
        assert framework.expert_review_triggers is not None
        assert framework.expert_review_triggers.overall_triggers[0].action == "进入专家复核"
        assert framework.anchors is not None
        assert framework.anchors.positive[0].source == "法学研究 2016年第4期"
        assert framework.anchors.negative[0].reason == "追热点式选题，问题虚构"
        assert framework.raw_config["dimensions"][0]["ceiling_rules"]
        assert framework.raw_config["governance_appendix"]["expert_review_triggers"]
        assert framework.raw_config["governance_appendix"]["sample_anchors"]["positive"][0]["type"] == "理论型"
        assert framework.raw_config["enums"]["review_flags"]["common"]
        assert framework.raw_config["output_constraints"]["dimension_max_chars"] == 500
