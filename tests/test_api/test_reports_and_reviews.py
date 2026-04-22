from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.report import Report
from tests.test_api.conftest import create_user
from tests.test_api.test_papers_router import FakeProvider, _install_sync_pipeline


def _login(client: TestClient, email: str, password: str = "secret123") -> None:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200


def _upload_with_scores(
    client: TestClient,
    provider_scores: list[int],
) -> dict:
    providers = [
        FakeProvider(f"mock-{index}", score)
        for index, score in enumerate(provider_scores, start=1)
    ]
    _install_sync_pipeline(client, providers)
    response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文内容".encode("utf-8"), "text/plain")},
        data={"provider_names": ",".join(provider.model_name for provider in providers)},
    )
    assert response.status_code == 202
    payload = response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202
    return payload


def test_internal_and_public_report_endpoints_expose_different_detail_levels(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter", display_name="Submitter")
    create_user(db_session, email="editor@example.com", role="editor", display_name="Editor")

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [80, 82, 84])

    client.cookies.clear()
    _login(client, "editor@example.com")
    internal_response = client.get(f"/api/papers/{payload['paper_id']}/internal-report")
    assert internal_response.status_code == 200
    internal_body = internal_response.json()
    assert internal_body["report_type"] == "internal"
    assert "model_scores" in internal_body["dimensions"][0]["ai"]

    client.cookies.clear()
    _login(client, "submitter@example.com")
    public_response = client.get(f"/api/papers/{payload['paper_id']}/report")
    assert public_response.status_code == 200
    public_body = public_response.json()
    assert public_body["report_type"] == "public"
    assert "model_scores" not in public_body["dimensions"][0]["ai"]


def test_report_export_supports_json_and_pdf(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [78, 79, 80])

    client.cookies.clear()
    _login(client, "editor@example.com")
    json_export = client.get(
        f"/api/papers/{payload['paper_id']}/report/export",
        params={"format": "json", "report_type": "internal"},
    )
    assert json_export.status_code == 200
    assert json_export.headers["content-type"].startswith("application/json")

    pdf_export = client.get(
        f"/api/papers/{payload['paper_id']}/report/export",
        params={"format": "pdf", "report_type": "internal"},
    )
    assert pdf_export.status_code == 200
    assert pdf_export.headers["content-type"].startswith("application/pdf")
    assert pdf_export.content.startswith(b"%PDF")


def test_expert_report_access_requires_assignment(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")
    assigned_expert = create_user(db_session, email="expert-assigned@example.com", role="expert")
    create_user(db_session, email="expert-unassigned@example.com", role="expert")
    client.app.state.email_sender = lambda **kwargs: None

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [80, 82, 84])

    client.cookies.clear()
    _login(client, "editor@example.com")
    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [assigned_expert.id]},
    )
    assert assign_response.status_code == 201

    client.cookies.clear()
    _login(client, "expert-unassigned@example.com")
    public_report_response = client.get(f"/api/papers/{payload['paper_id']}/report")
    public_history_response = client.get(
        f"/api/papers/{payload['paper_id']}/report/history",
        params={"report_type": "public"},
    )

    assert public_report_response.status_code == 403
    assert public_history_response.status_code == 403

    client.cookies.clear()
    _login(client, "expert-assigned@example.com")
    assigned_report_response = client.get(f"/api/papers/{payload['paper_id']}/report")

    assert assigned_report_response.status_code == 200


def test_low_confidence_task_appears_in_review_queue_and_editor_can_assign_expert(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    editor = create_user(db_session, email="editor@example.com", role="editor")
    expert = create_user(db_session, email="expert@example.com", role="expert")
    sent_notifications: list[dict] = []
    client.app.state.email_sender = lambda **kwargs: sent_notifications.append(kwargs)

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [40, 75, 95])

    client.cookies.clear()
    _login(client, "editor@example.com")
    queue_response = client.get("/api/reviews/queue")
    assert queue_response.status_code == 200
    assert queue_response.json()["items"][0]["task_id"] == payload["task_id"]
    assert queue_response.json()["items"][0]["assigned_reviews"] == []
    assert queue_response.json()["items"][0]["needs_assignment"] is True

    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [expert.id]},
    )
    assert assign_response.status_code == 201
    assert assign_response.json()["assigned_count"] == 1
    assert sent_notifications[0]["expert_email"] == "expert@example.com"


def test_review_queue_exposes_assignment_summaries_for_editor_workspace(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")
    expert = create_user(
        db_session,
        email="expert@example.com",
        role="expert",
        display_name="Primary Expert",
    )
    client.app.state.email_sender = lambda **kwargs: None

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [40, 75, 95])

    client.cookies.clear()
    _login(client, "editor@example.com")
    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [expert.id]},
    )
    assert assign_response.status_code == 201

    queue_response = client.get("/api/reviews/queue")

    assert queue_response.status_code == 200
    item = queue_response.json()["items"][0]
    assert item["task_id"] == payload["task_id"]
    assert item["task_status"] == "reviewing"
    assert item["needs_assignment"] is False
    assert item["assigned_reviews"] == [
        {
            "review_id": assign_response.json()["review_ids"][0],
            "expert_id": expert.id,
            "expert_email": "expert@example.com",
            "expert_display_name": "Primary Expert",
            "status": "pending",
            "completed_at": None,
        }
    ]


def test_expert_can_submit_review_and_internal_report_contains_feedback(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")
    expert = create_user(db_session, email="expert@example.com", role="expert")
    client.app.state.email_sender = lambda **kwargs: None

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [45, 70, 95])

    client.cookies.clear()
    _login(client, "editor@example.com")
    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [expert.id]},
    )
    assert assign_response.status_code == 201

    client.cookies.clear()
    _login(client, "expert@example.com")
    mine_response = client.get("/api/reviews/mine")
    assert mine_response.status_code == 200
    review_id = mine_response.json()["items"][0]["review_id"]

    submit_response = client.post(
        f"/api/reviews/{review_id}/submit",
        json={
            "comments": [
                {
                    "dimension_key": key,
                    "ai_score": 70,
                    "expert_score": 72,
                    "reason": "专家修正意见",
                }
                for key in [
                    "problem_originality",
                    "literature_insight",
                    "analytical_framework",
                    "logical_coherence",
                    "conclusion_consensus",
                    "forward_extension",
                ]
            ]
        },
    )
    assert submit_response.status_code == 200

    client.cookies.clear()
    _login(client, "editor@example.com")
    internal_response = client.get(f"/api/papers/{payload['paper_id']}/internal-report")
    assert internal_response.status_code == 200
    assert internal_response.json()["expert_reviews"][0]["expert_id"] == expert.id


def test_expert_review_list_includes_paper_context_for_workspace(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")
    expert = create_user(db_session, email="expert@example.com", role="expert")
    client.app.state.email_sender = lambda **kwargs: None

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [45, 70, 95])

    client.cookies.clear()
    _login(client, "editor@example.com")
    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [expert.id]},
    )
    assert assign_response.status_code == 201

    client.cookies.clear()
    _login(client, "expert@example.com")
    mine_response = client.get("/api/reviews/mine")

    assert mine_response.status_code == 200
    item = mine_response.json()["items"][0]
    assert item["review_id"]
    assert item["task_id"] == payload["task_id"]
    assert item["paper_id"] == payload["paper_id"]
    assert item["paper_title"] == "paper"


def test_report_history_lists_versions_and_supports_loading_specific_snapshot(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")
    expert = create_user(db_session, email="expert@example.com", role="expert")
    client.app.state.email_sender = lambda **kwargs: None

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [45, 70, 95])

    client.cookies.clear()
    _login(client, "editor@example.com")
    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [expert.id]},
    )
    assert assign_response.status_code == 201

    client.cookies.clear()
    _login(client, "expert@example.com")
    mine_response = client.get("/api/reviews/mine")
    assert mine_response.status_code == 200
    review_id = mine_response.json()["items"][0]["review_id"]
    submit_response = client.post(
        f"/api/reviews/{review_id}/submit",
        json={
            "comments": [
                {
                    "dimension_key": key,
                    "ai_score": 70,
                    "expert_score": 72,
                    "reason": "生成新报告版本",
                }
                for key in [
                    "problem_originality",
                    "literature_insight",
                    "analytical_framework",
                    "logical_coherence",
                    "conclusion_consensus",
                    "forward_extension",
                ]
            ]
        },
    )
    assert submit_response.status_code == 200

    client.cookies.clear()
    _login(client, "editor@example.com")
    history_response = client.get(
        f"/api/papers/{payload['paper_id']}/report/history",
        params={"report_type": "internal"},
    )
    assert history_response.status_code == 200
    history_body = history_response.json()
    assert [item["version"] for item in history_body["items"]] == [2, 1]
    assert history_body["items"][0]["is_current"] is True
    assert history_body["items"][1]["is_current"] is False
    assert history_body["items"][0]["available_export_formats"] == ["json", "pdf"]

    previous_report = client.get(
        f"/api/papers/{payload['paper_id']}/internal-report",
        params={"version": 1},
    )
    assert previous_report.status_code == 200
    assert previous_report.json()["expert_reviews"] == []

    current_report = client.get(f"/api/papers/{payload['paper_id']}/internal-report")
    assert current_report.status_code == 200
    assert current_report.json()["expert_reviews"][0]["expert_id"] == expert.id


def test_report_export_can_target_a_historical_snapshot(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")
    create_user(db_session, email="editor@example.com", role="editor")
    expert = create_user(db_session, email="expert@example.com", role="expert")
    client.app.state.email_sender = lambda **kwargs: None

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [45, 70, 95])

    client.cookies.clear()
    _login(client, "editor@example.com")
    assign_response = client.post(
        f"/api/reviews/{payload['task_id']}/assign",
        json={"expert_ids": [expert.id]},
    )
    assert assign_response.status_code == 201

    client.cookies.clear()
    _login(client, "expert@example.com")
    review_id = client.get("/api/reviews/mine").json()["items"][0]["review_id"]
    submit_response = client.post(
        f"/api/reviews/{review_id}/submit",
        json={
            "comments": [
                {
                    "dimension_key": key,
                    "ai_score": 70,
                    "expert_score": 72,
                    "reason": "导出历史版本",
                }
                for key in [
                    "problem_originality",
                    "literature_insight",
                    "analytical_framework",
                    "logical_coherence",
                    "conclusion_consensus",
                    "forward_extension",
                ]
            ]
        },
    )
    assert submit_response.status_code == 200

    client.cookies.clear()
    _login(client, "editor@example.com")
    json_export = client.get(
        f"/api/papers/{payload['paper_id']}/report/export",
        params={"format": "json", "report_type": "internal", "version": 1},
    )
    assert json_export.status_code == 200
    assert json_export.json()["expert_reviews"] == []

    pdf_export = client.get(
        f"/api/papers/{payload['paper_id']}/report/export",
        params={"format": "pdf", "report_type": "internal", "version": 1},
    )
    assert pdf_export.status_code == 200
    assert pdf_export.content.startswith(b"%PDF")


def test_report_dimension_scores_round_to_two_decimal_places(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [81, 82, 84])

    public_response = client.get(f"/api/papers/{payload['paper_id']}/report")
    assert public_response.status_code == 200
    dimension_ai = public_response.json()["dimensions"][0]["ai"]
    assert dimension_ai["mean_score"] == 82.33
    assert dimension_ai["std_score"] == 1.53


def test_rejected_precheck_report_exposes_rejection_without_fabricated_dimension_scores(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")

    _login(client, "submitter@example.com")
    _install_sync_pipeline(
        client,
        [
            FakeProvider("mock-a", 10, precheck_status="reject"),
            FakeProvider("mock-b", 20, precheck_status="reject"),
            FakeProvider("mock-c", 30, precheck_status="reject"),
        ],
    )
    upload_response = client.post(
        "/api/papers",
        files={"file": ("paper.txt", "正文".encode("utf-8"), "text/plain")},
        data={"provider_names": "mock-a,mock-b,mock-c"},
    )
    assert upload_response.status_code == 202
    payload = upload_response.json()
    start_response = client.post(f"/api/papers/{payload['paper_id']}/start")
    assert start_response.status_code == 202

    report_response = client.get(f"/api/papers/{payload['paper_id']}/report")

    assert report_response.status_code == 200
    body = report_response.json()
    assert body["precheck_status"] == "reject"
    assert body["precheck_result"]["status"] == "reject"
    assert body["dimensions"] == []
    assert body["weighted_total"] == 0.0

    history_response = client.get(f"/api/papers/{payload['paper_id']}/report/history")
    assert history_response.status_code == 200
    assert history_response.json()["items"][0]["precheck_status"] == "reject"


def test_report_endpoint_backfills_missing_evaluation_config_for_legacy_snapshots(
    client: TestClient, db_session: Session
) -> None:
    create_user(db_session, email="submitter@example.com", role="submitter")

    _login(client, "submitter@example.com")
    payload = _upload_with_scores(client, [80, 82, 84])

    public_report = (
        db_session.query(Report)
        .filter(Report.task_id == payload["task_id"], Report.report_type == "public", Report.is_current.is_(True))
        .first()
    )
    assert public_report is not None
    legacy_payload = dict(public_report.report_data)
    legacy_payload.pop("evaluation_config", None)
    public_report.report_data = legacy_payload
    db_session.add(public_report)
    db_session.commit()

    response = client.get(f"/api/papers/{payload['paper_id']}/report")

    assert response.status_code == 200
    assert response.json()["evaluation_config"] == {
        "selected_models": ["mock-1", "mock-2", "mock-3"],
        "evaluation_rounds": 1,
    }
