"""Tests for precheck runtime adaptation and v2.3 fields."""
from __future__ import annotations

from src.evaluation.precheck import (
    PrecheckModelResult,
    PrecheckResult,
    aggregate_precheck_results,
)
from src.reporting.builder import TERMINAL_PRECHECK_STATUSES


class TestPrecheckResultV23Fields:
    """Tests for PrecheckResult accepting v2.3 fields."""

    def test_precheck_result_accepts_evidence_quotes(self):
        """PrecheckResult should accept evidence_quotes field."""
        result = PrecheckResult(
            status="reject",
            issues=["Academic ethics violation"],
            recommendation="Reject the paper",
            evidence_quotes=[
                "Paragraph 3 contains copied text from Smith 2020",
                "Figure 2 appears to be duplicated from prior publication",
            ],
        )
        assert result.evidence_quotes == [
            "Paragraph 3 contains copied text from Smith 2020",
            "Figure 2 appears to be duplicated from prior publication",
        ]

    def test_precheck_result_accepts_review_flags(self):
        """PrecheckResult should accept review_flags field."""
        result = PrecheckResult(
            status="manual_review",
            issues=["Potential plagiarism detected"],
            recommendation="Requires expert review",
            review_flags=["plagiarism_suspected", "data_anomaly"],
        )
        assert result.review_flags == ["plagiarism_suspected", "data_anomaly"]

    def test_precheck_result_v23_fields_default_to_empty_list(self):
        """v2.3 fields should default to empty lists."""
        result = PrecheckResult(
            status="pass",
            issues=[],
            recommendation="Proceed to evaluation",
        )
        assert result.evidence_quotes == []
        assert result.review_flags == []

    def test_precheck_result_with_all_v23_fields(self):
        """PrecheckResult should work with all v2.3 fields populated."""
        result = PrecheckResult(
            status="manual_review",
            issues=["Issue 1", "Issue 2"],
            recommendation="Manual review needed",
            evidence_quotes=["Quote 1", "Quote 2"],
            review_flags=["flag_a", "flag_b"],
        )
        assert result.status == "manual_review"
        assert result.issues == ["Issue 1", "Issue 2"]
        assert result.recommendation == "Manual review needed"
        assert result.evidence_quotes == ["Quote 1", "Quote 2"]
        assert result.review_flags == ["flag_a", "flag_b"]

    def test_precheck_result_model_dump_includes_v23_fields(self):
        """model_dump should include v2.3 fields."""
        result = PrecheckResult(
            status="reject",
            issues=["Ethical violation"],
            evidence_quotes=["Evidence text"],
            review_flags=["ethics_violation"],
        )
        dumped = result.model_dump()
        assert "evidence_quotes" in dumped
        assert "review_flags" in dumped
        assert dumped["evidence_quotes"] == ["Evidence text"]
        assert dumped["review_flags"] == ["ethics_violation"]


class TestTerminalPrecheckStatuses:
    """Tests for terminal precheck status handling."""

    def test_reject_is_terminal_status(self):
        """'reject' should be a terminal precheck status."""
        assert "reject" in TERMINAL_PRECHECK_STATUSES

    def test_manual_review_is_not_terminal_status(self):
        """'manual_review' should NOT be a terminal precheck status anymore."""
        assert "manual_review" not in TERMINAL_PRECHECK_STATUSES

    def test_pass_is_not_terminal_status(self):
        """'pass' should NOT be a terminal precheck status."""
        assert "pass" not in TERMINAL_PRECHECK_STATUSES

    def test_conditional_pass_is_not_terminal_status(self):
        """'conditional_pass' should NOT be a terminal precheck status."""
        assert "conditional_pass" not in TERMINAL_PRECHECK_STATUSES

    def test_terminal_statuses_count(self):
        """There should be exactly 1 terminal status."""
        assert len(TERMINAL_PRECHECK_STATUSES) == 1


class TestPrecheckStatusFlow:
    """Tests for precheck status flow decisions."""

    def test_manual_review_is_soft_flag_for_aggregator(self):
        """manual_review should be treated as soft flag, not hard stop."""
        precheck = PrecheckResult(
            status="manual_review",
            issues=["Requires expert judgment"],
            review_flags=["complex_methodology"],
        )
        assert precheck.status == "manual_review"
        assert precheck.status not in TERMINAL_PRECHECK_STATUSES

    def test_reject_triggers_completed_state(self):
        """reject status should trigger completed state."""
        precheck = PrecheckResult(
            status="reject",
            issues=["Failed academic ethics check"],
            evidence_quotes=["Evidence of plagiarism"],
        )
        assert precheck.status == "reject"
        assert precheck.status in TERMINAL_PRECHECK_STATUSES

    def test_pass_allows_scoring_continuation(self):
        """pass status should allow scoring to continue."""
        precheck = PrecheckResult(
            status="pass",
            issues=[],
            recommendation="Proceed to full evaluation",
        )
        assert precheck.status == "pass"
        assert precheck.status not in TERMINAL_PRECHECK_STATUSES

    def test_conditional_pass_allows_scoring_continuation(self):
        """conditional_pass status should allow scoring to continue."""
        precheck = PrecheckResult(
            status="conditional_pass",
            issues=["Minor formatting issues"],
            recommendation="Proceed with note",
        )
        assert precheck.status == "conditional_pass"
        assert precheck.status not in TERMINAL_PRECHECK_STATUSES


class TestAggregatedPrecheckResult:
    """Tests for multi-model precheck aggregation."""

    def test_two_reject_votes_become_hard_reject(self):
        result = aggregate_precheck_results(
            [
                PrecheckModelResult(model_name="model-a", status="reject", issues=["不可评"], review_flags=["ethics_risk"]),
                PrecheckModelResult(model_name="model-b", status="reject", issues=["严重缺页"], review_flags=["writing_risk"]),
                PrecheckModelResult(model_name="model-c", status="pass", issues=[]),
            ]
        )

        assert result.status == "reject"
        assert result.blocking_vote_count == 2
        assert result.total_models == 3
        assert result.decision_rule == "2_of_3_blocking_consensus"
        assert len(result.per_model) == 3

    def test_manual_review_and_conditional_pass_become_conditional_pass(self):
        result = aggregate_precheck_results(
            [
                PrecheckModelResult(
                    model_name="model-a",
                    status="manual_review",
                    issues=["需人工复核"],
                    review_flags=["citation_risk"],
                ),
                PrecheckModelResult(model_name="model-b", status="pass", issues=[]),
                PrecheckModelResult(
                    model_name="model-c",
                    status="conditional_pass",
                    issues=["有轻微引注问题"],
                    review_flags=["writing_risk"],
                ),
            ]
        )

        assert result.status == "conditional_pass"
        assert result.blocking_vote_count == 0
        assert sorted(result.review_flags) == ["citation_risk", "writing_risk"]
        assert result.consensus["status"] == "conditional_pass"

    def test_all_pass_stays_pass(self):
        result = aggregate_precheck_results(
            [
                PrecheckModelResult(model_name="model-a", status="pass", issues=[]),
                PrecheckModelResult(model_name="model-b", status="pass", issues=[]),
                PrecheckModelResult(model_name="model-c", status="pass", issues=[]),
            ]
        )

        assert result.status == "pass"
        assert result.review_flags == ["none"]
        assert result.consensus["status"] == "pass"
