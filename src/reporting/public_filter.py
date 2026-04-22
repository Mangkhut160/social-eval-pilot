from __future__ import annotations


def build_public_report(internal_report: dict) -> dict:
    public_dimensions = []
    for dimension in internal_report["dimensions"]:
        public_dimension = {
            "key": dimension["key"],
            "name_zh": dimension["name_zh"],
            "name_en": dimension["name_en"],
            "weight": dimension["weight"],
            "ai": {
                "evidence_quotes": dimension["ai"].get("evidence_quotes", []),
                "analysis": dimension["ai"].get("analysis", []),
            },
        }
        consensus = dimension.get("consensus")
        if isinstance(consensus, dict):
            public_consensus = dict(consensus)
            public_consensus.pop("model_scores", None)
            public_dimension["consensus"] = public_consensus
        public_dimensions.append(public_dimension)

    public_precheck_result = internal_report.get("precheck_result")
    if isinstance(public_precheck_result, dict):
        public_precheck_result = dict(public_precheck_result)
        public_precheck_result.pop("per_model", None)

    expert_summaries = []
    for review in internal_report["expert_reviews"]:
        expert_summaries.append(
            {
                "review_id": review["review_id"],
                "status": review["status"],
                "comments": [
                    {
                        "dimension_key": comment["dimension_key"],
                        "expert_score": comment["expert_score"],
                        "reason": comment["reason"],
                    }
                    for comment in review["comments"]
                ],
            }
        )

    return {
        "report_type": "public",
        "paper_id": internal_report["paper_id"],
        "task_id": internal_report["task_id"],
        "paper_title": internal_report["paper_title"],
        "precheck_status": internal_report.get("precheck_status"),
        "precheck_result": public_precheck_result,
        "evaluation_config": internal_report.get("evaluation_config"),
        "weighted_total": internal_report["weighted_total"],
        "radar_chart": internal_report["radar_chart"],
        "dimensions": public_dimensions,
        "expert_reviews": expert_summaries,
    }
