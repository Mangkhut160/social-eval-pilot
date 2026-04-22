import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import * as api from "./lib/api";

vi.mock("./lib/api", () => ({
  acceptInvitation: vi.fn(),
  assignExpert: vi.fn(),
  closeAdminTask: vi.fn(),
  createInvitation: vi.fn(),
  deletePaper: vi.fn(),
  listAuditLogs: vi.fn(),
  getCurrentUser: vi.fn(),
  listInvitations: vi.fn(),
  getPaperOptions: vi.fn(),
  getInternalReport: vi.fn(),
  getPaperStatus: vi.fn(),
  getPublicReport: vi.fn(),
  getRecoveryTasks: vi.fn(),
  getReportExportUrl: vi.fn(),
  getReviewQueue: vi.fn(),
  listExperts: vi.fn(),
  listMyReviews: vi.fn(),
  listPapers: vi.fn(),
  listReportHistory: vi.fn(),
  listUsers: vi.fn(),
  login: vi.fn(),
  retryAdminTask: vi.fn(),
  revokeInvitation: vi.fn(),
  logout: vi.fn(),
  startPaperEvaluation: vi.fn(),
  submitReview: vi.fn(),
  uploadPaper: vi.fn(),
}));

const mockedApi = vi.mocked(api);
const RADAR_CHART_IMAGE_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO2l0WQAAAAASUVORK5CYII=";

const paperItems = [
  {
    paper_id: "paper-1",
    title: "Platform Governance Study",
    original_filename: "platform-governance.txt",
    paper_status: "completed",
    precheck_status: "passed",
  },
  {
    paper_id: "paper-2",
    title: "Comparative Law Notes",
    original_filename: "comparative-law.docx",
    paper_status: "pending",
    precheck_status: null,
  },
  {
    paper_id: "paper-3",
    title: "Rejected Draft",
    original_filename: "rejected-draft.pdf",
    paper_status: "completed",
    precheck_status: "reject",
  },
];

const statusItems = {
  "paper-1": {
    paper_id: "paper-1",
    task_id: "task-1",
    paper_status: "completed",
    task_status: "completed",
    precheck_status: "passed",
    reliability_summary: {
      total_dimensions: 6,
      high_confidence_count: 5,
      low_confidence_count: 1,
      overall_high_confidence: false,
    },
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1", "qwen/qwen3.6-plus"],
      evaluation_rounds: 2,
    },
  },
  "paper-2": {
    paper_id: "paper-2",
    task_id: "task-2",
    paper_status: "pending",
    task_status: "pending",
    precheck_status: null,
    reliability_summary: null,
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1"],
      evaluation_rounds: 1,
    },
  },
  "paper-3": {
    paper_id: "paper-3",
    task_id: "task-3",
    paper_status: "completed",
    task_status: "completed",
    precheck_status: "reject",
    reliability_summary: null,
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1"],
      evaluation_rounds: 1,
    },
  },
} as const;

const paperOptions = {
  model_options: [
    { name: "z-ai/glm-5.1", label: "z-ai/glm-5.1", source: "zenmux" },
    { name: "qwen/qwen3.6-plus", label: "qwen/qwen3.6-plus", source: "zenmux" },
    { name: "openai/gpt-5.4", label: "openai/gpt-5.4", source: "zenmux" },
  ],
  default_selected_models: ["z-ai/glm-5.1", "qwen/qwen3.6-plus"],
  max_selected_models: 3,
  default_rounds: 2,
  min_rounds: 1,
  max_rounds: 5,
} as const;

const reportHistoryItems = {
  "paper-1": [
    {
      report_id: "report-2",
      report_type: "public",
      version: 2,
      is_current: true,
      weighted_total: 82,
      precheck_status: "passed",
      created_at: "2026-04-16T12:00:00Z",
      available_export_formats: ["json", "pdf"],
    },
    {
      report_id: "report-1",
      report_type: "public",
      version: 1,
      is_current: false,
      weighted_total: 79,
      precheck_status: "passed",
      created_at: "2026-04-16T11:30:00Z",
      available_export_formats: ["json", "pdf"],
    },
  ],
  "paper-2": [],
  "paper-3": [
    {
      report_id: "report-3",
      report_type: "public",
      version: 1,
      is_current: true,
      weighted_total: 0,
      precheck_status: "reject",
      created_at: "2026-04-16T12:30:00Z",
      available_export_formats: ["json", "pdf"],
    },
  ],
} as const;

const reports = {
  "paper-1:current": {
    report_type: "public",
    paper_id: "paper-1",
    task_id: "task-1",
    paper_title: "Platform Governance Study",
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1", "qwen/qwen3.6-plus"],
      evaluation_rounds: 2,
    },
    weighted_total: 82,
    dimensions: [
      {
        key: "problem_originality",
        name_zh: "问题创新性",
        name_en: "Problem Originality",
        weight: 1 / 6,
        ai: { mean_score: 84, std_score: 3, is_high_confidence: true },
      },
    ],
    expert_reviews: [
      {
        review_id: "review-1",
        status: "submitted",
        comments: [
          {
            dimension_key: "problem_originality",
            expert_score: 86,
            reason: "问题定义准确，且具备现实政策价值。",
          },
        ],
      },
      {
        review_id: "review-2",
        status: "submitted",
        comments: [
          {
            dimension_key: "problem_originality",
            expert_score: 83.5,
            reason: "选题切口清晰，但部分案例比较仍可补强。",
          },
        ],
      },
    ],
    radar_chart: {
      labels: ["问题创新性", "理论建构力", "材料支撑"],
      values: [84, 80, 81],
      image_base64: RADAR_CHART_IMAGE_BASE64,
    },
  },
  "paper-1:1": {
    report_type: "public",
    paper_id: "paper-1",
    task_id: "task-1",
    paper_title: "Platform Governance Study",
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1", "qwen/qwen3.6-plus"],
      evaluation_rounds: 2,
    },
    weighted_total: 79,
    dimensions: [
      {
        key: "problem_originality",
        name_zh: "问题创新性",
        name_en: "Problem Originality",
        weight: 1 / 6,
        ai: { mean_score: 78, std_score: 4, is_high_confidence: false },
      },
    ],
    expert_reviews: [],
  },
  "paper-2:current": {
    report_type: "public",
    paper_id: "paper-2",
    task_id: "task-2",
    paper_title: "Comparative Law Notes",
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1"],
      evaluation_rounds: 1,
    },
    weighted_total: 0,
    dimensions: [],
    expert_reviews: [],
  },
  "paper-3:current": {
    report_type: "public",
    paper_id: "paper-3",
    task_id: "task-3",
    paper_title: "Rejected Draft",
    precheck_status: "reject",
    precheck_result: {
      status: "reject",
      issues: ["Missing reference list", "Missing Figure 1"],
      recommendation: "Revise submission before scoring.",
    },
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1"],
      evaluation_rounds: 1,
    },
    weighted_total: 0,
    dimensions: [],
    expert_reviews: [],
  },
} as const;

const internalReports = {
  "paper-1": {
    report_type: "internal",
    paper_id: "paper-1",
    task_id: "task-1",
    paper_title: "Platform Governance Study",
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1", "qwen/qwen3.6-plus"],
      evaluation_rounds: 2,
    },
    weighted_total: 82,
    dimensions: [
      {
        key: "problem_originality",
        name_zh: "问题创新性",
        name_en: "Problem Originality",
        weight: 1 / 6,
        ai: {
          mean_score: 84,
          std_score: 3,
          is_high_confidence: true,
          model_scores: {
            "z-ai/glm-5.1": 82.5,
            "qwen/qwen3.6-plus": 85.5,
          },
          evidence_quotes: [
            "论文提出“平台治理中的双重规制困境”，问题识别准确。",
            "第二章给出可操作的比较法框架，支持创新性判断。",
          ],
          analysis: ["该维度模型分歧较小，结论稳定。"],
        },
      },
      {
        key: "analytical_framework",
        name_zh: "理论建构力",
        name_en: "Analytical Framework",
        weight: 1 / 6,
        ai: {
          mean_score: 80,
          std_score: 4,
          is_high_confidence: false,
          model_scores: {
            "z-ai/glm-5.1": 77.5,
            "qwen/qwen3.6-plus": 82.5,
          },
          evidence_quotes: ["理论章节结构清晰，但中层概念定义仍可收敛。"],
          analysis: ["该维度存在轻微模型分歧，建议人工复核。"],
        },
      },
    ],
    expert_reviews: [
      {
        review_id: "review-internal-1",
        status: "submitted",
        comments: [
          {
            dimension_key: "analytical_framework",
            expert_score: 78.25,
            reason: "理论结构完整，但核心概念边界需要进一步明确。",
          },
        ],
      },
      {
        review_id: "review-internal-2",
        status: "pending",
        comments: [
          {
            dimension_key: "problem_originality",
            expert_score: 85,
            reason: "问题识别到位，但政策场景覆盖还可更完整。",
          },
        ],
      },
    ],
    radar_chart: {
      labels: ["问题创新性", "理论建构力", "材料支撑"],
      values: [84, 80, 81],
      image_base64: RADAR_CHART_IMAGE_BASE64,
    },
  },
  "paper-4": {
    report_type: "internal",
    paper_id: "paper-4",
    task_id: "task-4",
    paper_title: "Digital Humanities Draft",
    evaluation_config: {
      selected_models: ["z-ai/glm-5.1", "openai/gpt-5.4"],
      evaluation_rounds: 2,
    },
    weighted_total: 76.5,
    dimensions: [
      {
        key: "problem_originality",
        name_zh: "问题创新性",
        name_en: "Problem Originality",
        weight: 1 / 6,
        ai: {
          mean_score: 74.25,
          std_score: 6.5,
          is_high_confidence: false,
          model_scores: {
            "z-ai/glm-5.1": 71.25,
            "openai/gpt-5.4": 77.25,
          },
          evidence_quotes: ["研究问题具有跨学科价值，但具体切口需进一步收敛。"],
          analysis: ["该维度波动较高，建议优先安排专家复核。"],
        },
      },
      {
        key: "forward_extension",
        name_zh: "延展潜力",
        name_en: "Forward Extension",
        weight: 1 / 6,
        ai: {
          mean_score: 79.5,
          std_score: 2.15,
          is_high_confidence: true,
          model_scores: {
            "z-ai/glm-5.1": 78,
            "openai/gpt-5.4": 81,
          },
          evidence_quotes: ["结论部分提出了可扩展的后续研究路径。"],
          analysis: ["该维度稳定，暂不需要额外人工干预。"],
        },
      },
    ],
    expert_reviews: [
      {
        review_id: "review-internal-2",
        status: "submitted",
        comments: [
          {
            dimension_key: "problem_originality",
            expert_score: 76,
            reason: "研究问题有价值，但需在案例选择上进一步聚焦。",
          },
        ],
      },
    ],
    radar_chart: {
      labels: ["问题创新性", "延展潜力", "材料支撑"],
      values: [74.25, 79.5, 76],
      image_base64: RADAR_CHART_IMAGE_BASE64,
    },
  },
} as const;

const reviewQueueItems = [
  {
    task_id: "task-1",
    paper_id: "paper-1",
    paper_title: "Platform Governance Study",
    paper_status: "reviewing",
    task_status: "reviewing",
    low_confidence_dimensions: ["理论建构力"],
    needs_assignment: false,
    assigned_reviews: [
      {
        review_id: "review-queued-1",
        expert_id: "expert-1",
        expert_email: "expert.one@example.com",
        expert_display_name: "Primary Expert",
        status: "pending",
        completed_at: null,
      },
    ],
  },
  {
    task_id: "task-4",
    paper_id: "paper-4",
    paper_title: "Digital Humanities Draft",
    paper_status: "reviewing",
    task_status: "reviewing",
    low_confidence_dimensions: ["问题创新性", "延展潜力"],
    needs_assignment: true,
    assigned_reviews: [],
  },
] as const;

const expertUsers = [
  {
    id: "expert-1",
    email: "expert.one@example.com",
    role: "expert",
    display_name: "Primary Expert",
    is_active: true,
  },
  {
    id: "expert-2",
    email: "expert.two@example.com",
    role: "expert",
    display_name: "Second Expert",
    is_active: true,
  },
] as const;

const invitationItems = [
  {
    id: "invite-1",
    email: "pending.editor@example.com",
    role: "editor",
    token: "token-editor-1",
    invited_by: "user-3",
    is_used: false,
    expires_at: "2026-04-25T08:00:00Z",
    created_at: "2026-04-18T08:00:00Z",
  },
  {
    id: "invite-2",
    email: "used.editor@example.com",
    role: "editor",
    token: "token-editor-2",
    invited_by: "user-3",
    is_used: true,
    expires_at: "2026-04-25T08:00:00Z",
    created_at: "2026-04-18T08:00:00Z",
  },
] as const;

const recoveryTaskItems = [
  {
    task_id: "task-recover-1",
    paper_id: "paper-recover-1",
    paper_title: "Needs Recovery Draft",
    paper_filename: "needs-recovery.txt",
    task_status: "recovering",
    paper_status: "processing",
    failure_stage: "evaluation",
    failure_detail: "provider timeout",
    created_at: "2026-04-18T08:05:00Z",
    updated_at: "2026-04-18T08:15:00Z",
  },
] as const;

const auditLogItems = [
  {
    id: "audit-1",
    actor_id: "user-3",
    actor_email: "admin@example.com",
    object_type: "evaluation_task",
    object_id: "task-recover-1",
    action: "retry_task",
    result: "completed",
    details: { paper_id: "paper-recover-1" },
    created_at: "2026-04-18T08:16:00Z",
  },
  {
    id: "audit-2",
    actor_id: "user-3",
    actor_email: "admin@example.com",
    object_type: "evaluation_task",
    object_id: "task-recover-2",
    action: "close_task",
    result: "closed",
    details: { paper_id: "paper-recover-2" },
    created_at: "2026-04-18T08:17:00Z",
  },
] as const;

function renderSubmitterApp() {
  return render(
    <App
      initialUser={{
        id: "user-1",
        email: "submitter@example.com",
        role: "submitter",
        display_name: "Submitter",
        is_active: true,
      }}
    />
  );
}

function renderExpertApp() {
  return render(
    <App
      initialUser={{
        id: "user-4",
        email: "expert@example.com",
        role: "expert",
        display_name: "Expert",
        is_active: true,
      }}
    />
  );
}

function renderEditorApp() {
  return render(
    <App
      initialUser={{
        id: "user-2",
        email: "editor@example.com",
        role: "editor",
        display_name: "Editor",
        is_active: true,
      }}
    />
  );
}

function renderAdminApp() {
  return render(
    <App
      initialUser={{
        id: "user-3",
        email: "admin@example.com",
        role: "admin",
        display_name: "Admin",
        is_active: true,
      }}
    />
  );
}

describe("App", () => {
  afterEach(() => {
    cleanup();
    window.history.pushState({}, "", "/");
  });

  beforeEach(() => {
    vi.clearAllMocks();
    mockedApi.listPapers.mockResolvedValue([...paperItems]);
    mockedApi.getPaperOptions.mockResolvedValue(paperOptions);
    mockedApi.getPaperStatus.mockImplementation(async (paperId: string) => statusItems[paperId as "paper-1" | "paper-2" | "paper-3"]);
    mockedApi.listReportHistory.mockImplementation(
      async (paperId: string) => [...reportHistoryItems[paperId as "paper-1" | "paper-2" | "paper-3"]]
    );
    mockedApi.getPublicReport.mockImplementation(async (paperId: string, version?: number) => {
      const key = `${paperId}:${version ?? "current"}` as keyof typeof reports;
      return reports[key];
    });
    mockedApi.getInternalReport.mockImplementation(
      async (paperId: string) => internalReports[paperId as keyof typeof internalReports]
    );
    mockedApi.getReportExportUrl.mockImplementation(
      (paperId: string, format: string, reportType = "public", version?: number) =>
        `/api/papers/${paperId}/report/export?format=${format}&report_type=${reportType}${version ? `&version=${version}` : ""}`
    );
    mockedApi.acceptInvitation.mockResolvedValue({
      id: "invited-user",
      email: "activated@example.com",
      role: "submitter",
      display_name: "Activated User",
      is_active: true,
    });
    (mockedApi as any).createInvitation.mockResolvedValue({
      id: "invite-created-default",
      email: "new-user@example.com",
      role: "submitter",
      token: "default-invite-token",
      expires_at: "2026-04-25T08:00:00Z",
    });
    mockedApi.uploadPaper.mockResolvedValue({ paper_id: "paper-3", task_id: "task-3" });
    mockedApi.startPaperEvaluation.mockResolvedValue({ paper_id: "paper-2", task_id: "task-2" });
    mockedApi.deletePaper.mockResolvedValue(undefined);
    mockedApi.getReviewQueue.mockResolvedValue([...reviewQueueItems]);
    mockedApi.listExperts.mockResolvedValue([...expertUsers]);
    mockedApi.assignExpert.mockResolvedValue(undefined);
    (mockedApi as any).listInvitations.mockResolvedValue([...invitationItems]);
    (mockedApi as any).revokeInvitation.mockResolvedValue(undefined);
    (mockedApi as any).getRecoveryTasks.mockResolvedValue([...recoveryTaskItems]);
    (mockedApi as any).retryAdminTask.mockResolvedValue(undefined);
    (mockedApi as any).closeAdminTask.mockResolvedValue(undefined);
    (mockedApi as any).listAuditLogs.mockImplementation(async (filters?: any) => {
      if (!filters?.action) {
        return [...auditLogItems];
      }
      return auditLogItems.filter((item) => item.action === filters.action);
    });
    mockedApi.listMyReviews.mockResolvedValue([
      {
        review_id: "review-1",
        task_id: "task-1",
        paper_id: "paper-1",
        paper_title: "Platform Governance Study",
        status: "pending",
      },
    ]);
    mockedApi.listUsers.mockResolvedValue([]);
  });

  it("shows the login form when there is no authenticated user", () => {
    render(<App initialUser={null} />);

    expect(screen.getByRole("heading", { name: /文科论文评价系统 登录/i })).toBeInTheDocument();
  });

  it("shows the invitation activation form when the invitation token is present", () => {
    window.history.pushState({}, "", "/?invitation_token=invite-123");

    render(<App initialUser={null} />);

    expect(screen.getByRole("heading", { name: /激活账号/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /完成激活/i })).toBeInTheDocument();
  });

  it("accepts an invitation and returns to a login-ready state", async () => {
    window.history.pushState({}, "", "/?invitation_token=invite-123");

    render(<App initialUser={null} />);

    fireEvent.change(screen.getByLabelText(/显示名称/i), {
      target: { value: "Activated User" },
    });
    fireEvent.change(screen.getByLabelText(/^密码$/i), {
      target: { value: "new-password-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /完成激活/i }));

    await waitFor(() => {
      expect(mockedApi.acceptInvitation).toHaveBeenCalledWith({
        token: "invite-123",
        displayName: "Activated User",
        password: "new-password-123",
      });
    });
    expect(await screen.findByRole("heading", { name: /文科论文评价系统 登录/i })).toBeInTheDocument();
    expect(screen.getByText(/账号已激活/i)).toBeInTheDocument();
    expect(screen.getByDisplayValue("activated@example.com")).toBeInTheDocument();
  });

  it("shows activation errors when invitation acceptance fails", async () => {
    mockedApi.acceptInvitation.mockRejectedValueOnce(new Error("Invitation has expired"));
    window.history.pushState({}, "", "/?invitation_token=invite-expired");

    render(<App initialUser={null} />);

    fireEvent.change(screen.getByLabelText(/显示名称/i), {
      target: { value: "Expired User" },
    });
    fireEvent.change(screen.getByLabelText(/^密码$/i), {
      target: { value: "new-password-123" },
    });
    fireEvent.click(screen.getByRole("button", { name: /完成激活/i }));

    expect(await screen.findByText(/invitation has expired/i)).toBeInTheDocument();
  });

  it("shows a submitter workspace with dropzone, paper list, and report history", async () => {
    renderSubmitterApp();

    expect(screen.getByRole("heading", { name: /文科论文评价系统/i })).toBeInTheDocument();
    expect(screen.getByText(/将稿件拖拽到这里/i)).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: /选择评测模型/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/评测轮数/i)).toHaveValue(2);
    expect(screen.getByRole("checkbox", { name: /z-ai\/glm-5\.1/i })).toBeChecked();
    expect(
      await screen.findByRole("button", { name: /打开 platform governance study/i })
    ).toBeInTheDocument();
    expect(screen.getByText(/报告历史/i)).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /版本 2（当前）/i })).toBeInTheDocument();
    expect(screen.getAllByText(/综合得分/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: /问题创新性/i })).toBeInTheDocument();
    expect(screen.getAllByText(/2 轮/i).length).toBeGreaterThan(0);
  });

  it("renders public report with radar and grouped expert comments only", async () => {
    renderSubmitterApp();

    expect(await screen.findByRole("img", { name: /维度雷达图/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /模型评分/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /证据摘录/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /AI 分析/i })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /专家复核意见/i })).toBeInTheDocument();
    expect(screen.getAllByText(/问题定义准确，且具备现实政策价值/i).length).toBeGreaterThan(0);
  });

  it("groups expert review comments by review submission", async () => {
    renderSubmitterApp();

    expect(await screen.findByText(/复核提交 review-1/i)).toBeInTheDocument();
    expect(screen.getByText(/复核提交 review-2/i)).toBeInTheDocument();
    expect(screen.getAllByText(/问题定义准确，且具备现实政策价值/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/选题切口清晰，但部分案例比较仍可补强/i).length).toBeGreaterThan(0);
  });

  it("loads a historical report snapshot when a version is selected", async () => {
    renderSubmitterApp();

    fireEvent.click(await screen.findByRole("button", { name: /版本 1（历史）/i }));

    await waitFor(() => {
      expect(mockedApi.getPublicReport).toHaveBeenCalledWith("paper-1", 1);
    });
    expect(screen.getByRole("button", { name: /版本 1（历史）/i })).toBeInTheDocument();
    expect(screen.getAllByText(/79\/100/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /下载 json/i })).toHaveAttribute(
      "href",
      expect.stringContaining("version=1")
    );
  });

  it("uploads a dropped file through the submitter dropzone", async () => {
    renderSubmitterApp();

    fireEvent.click(await screen.findByRole("checkbox", { name: /openai\/gpt-5\.4/i }));
    fireEvent.change(screen.getByLabelText(/评测轮数/i), {
      target: { value: "3" },
    });

    const dropzone = screen.getByTestId("paper-dropzone");
    const file = new File(["demo content"], "demo-paper.txt", { type: "text/plain" });
    fireEvent.drop(dropzone, {
      dataTransfer: {
        files: [file],
      },
    });

    await waitFor(() => {
      expect(mockedApi.uploadPaper).toHaveBeenCalledWith(file, {
        selectedModels: ["z-ai/glm-5.1", "qwen/qwen3.6-plus", "openai/gpt-5.4"],
        evaluationRounds: 3,
      });
    });
    expect(mockedApi.startPaperEvaluation).not.toHaveBeenCalled();
  });

  it("starts evaluation only after the submitter clicks the start button", async () => {
    renderSubmitterApp();

    fireEvent.click(await screen.findByRole("button", { name: /打开 comparative law notes/i }));
    fireEvent.click(await screen.findByRole("button", { name: /开始评测/i }));

    await waitFor(() => {
      expect(mockedApi.startPaperEvaluation).toHaveBeenCalledWith("paper-2");
    });
  });

  it("shows a precheck rejection summary instead of fake zero-dimension scores", async () => {
    renderSubmitterApp();

    fireEvent.click(await screen.findByRole("button", { name: /打开 rejected draft/i }));

    expect(await screen.findByRole("heading", { name: /预检未通过/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /版本 1（当前）/i })).toHaveTextContent(
      /预检拒稿/i
    );
    expect(screen.getAllByText(/missing reference list/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/建议：revise submission before scoring\./i).length).toBeGreaterThan(0);
    expect(screen.queryByText(/0\/100/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /问题创新性/i })).not.toBeInTheDocument();
  });

  it("shows product-oriented resubmission guidance for rejected submissions", async () => {
    renderSubmitterApp();

    const rejectedButton = await screen.findByRole("button", { name: /打开 rejected draft/i });
    fireEvent.click(rejectedButton);

    expect(rejectedButton).toHaveTextContent(/需重新上传/i);
    expect(await screen.findByText(/当前状态：需重新上传/i)).toBeInTheDocument();
    expect(
      screen.getByText(/请根据下列问题修改稿件后重新上传，再重新开始评测/i)
    ).toBeInTheDocument();
  });

  it("shows an action-oriented empty state before evaluation starts", async () => {
    renderSubmitterApp();

    fireEvent.click(await screen.findByRole("button", { name: /打开 comparative law notes/i }));

    expect(
      await screen.findByText(/该稿件已上传。请先点击“开始评测”，系统才会生成首个报告快照/i)
    ).toBeInTheDocument();
  });

  it("allows a submitter to delete a completed paper from the workspace", async () => {
    mockedApi.listPapers
      .mockResolvedValueOnce([...paperItems])
      .mockResolvedValueOnce([paperItems[1]]);

    renderSubmitterApp();

    fireEvent.click(await screen.findByRole("button", { name: /删除 platform governance study/i }));

    await waitFor(() => {
      expect(mockedApi.deletePaper).toHaveBeenCalledWith("paper-1");
    });
    await waitFor(() => {
      expect(
        screen.queryByRole("button", { name: /打开 platform governance study/i })
      ).not.toBeInTheDocument();
    });
  });

  it("shows the editor dashboard for editor users", () => {
    renderEditorApp();

    expect(screen.getByText(/编辑工作台/i)).toBeInTheDocument();
  });

  it("shows a real editor workspace with queue detail and multi-expert assignment", async () => {
    mockedApi.getReviewQueue
      .mockResolvedValueOnce([...reviewQueueItems])
      .mockResolvedValueOnce([
        {
          ...reviewQueueItems[0],
        },
        {
          ...reviewQueueItems[1],
          needs_assignment: false,
          assigned_reviews: [
            {
              review_id: "review-new-1",
              expert_id: "expert-1",
              expert_email: "expert.one@example.com",
              expert_display_name: "Primary Expert",
              status: "pending",
              completed_at: null,
            },
            {
              review_id: "review-new-2",
              expert_id: "expert-2",
              expert_email: "expert.two@example.com",
              expert_display_name: "Second Expert",
              status: "pending",
              completed_at: null,
            },
          ],
        },
      ]);

    renderEditorApp();

    expect(
      await screen.findByRole("button", { name: /打开 digital humanities draft/i })
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /打开 digital humanities draft/i }));

    expect(await screen.findByRole("heading", { name: /digital humanities draft/i })).toBeInTheDocument();
    expect(screen.getByText(/待复核维度：问题创新性、延展潜力/i)).toBeInTheDocument();
    expect(screen.getByText(/74\.25/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("checkbox", { name: /primary expert/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /second expert/i }));
    fireEvent.click(screen.getByRole("button", { name: /分配专家/i }));

    await waitFor(() => {
      expect(mockedApi.assignExpert).toHaveBeenCalledWith("task-4", ["expert-1", "expert-2"]);
    });
    expect(await screen.findByText(/已为当前任务分配 2 位专家/i)).toBeInTheDocument();
  });

  it("renders rich internal report details in editor workspace", async () => {
    renderEditorApp();

    const openDraft = await screen.findByRole("button", { name: /打开 digital humanities draft/i });
    fireEvent.click(openDraft);

    expect(await screen.findByRole("img", { name: /维度雷达图/i })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: /模型评分/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/openai\/gpt-5\.4/i).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: /证据摘录/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: /AI 分析/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/研究问题具有跨学科价值/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/建议优先安排专家复核/i).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: /专家复核意见/i })).toBeInTheDocument();
    expect(screen.getAllByText(/研究问题有价值，但需在案例选择上进一步聚焦/i).length).toBeGreaterThan(0);
  });

  it("shows the admin dashboard for admin users", () => {
    renderAdminApp();

    expect(screen.getByText(/管理工作台/i)).toBeInTheDocument();
  });

  it("renders admin roster with user active/inactive status context", async () => {
    mockedApi.listUsers.mockResolvedValueOnce([
      {
        id: "user-active",
        email: "active@example.com",
        role: "editor",
        display_name: "Active User",
        is_active: true,
      },
      {
        id: "user-inactive",
        email: "inactive@example.com",
        role: "expert",
        display_name: "Inactive User",
        is_active: false,
      },
    ]);

    renderAdminApp();

    expect(await screen.findByText(/active user - 编辑（启用）/i)).toBeInTheDocument();
    expect(screen.getByText(/inactive user - 专家（停用）/i)).toBeInTheDocument();
  });

  it("shows invitation management, recovery tasks, and audit logs in the admin dashboard", async () => {
    renderAdminApp();

    expect(screen.getByRole("heading", { name: /邀请管理/i })).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: /撤销邀请 pending\.editor@example\.com/i })
    ).toBeInTheDocument();
    expect(screen.queryByText(/used\.editor@example\.com/i)).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /任务恢复/i })).toBeInTheDocument();
    expect(await screen.findByText(/needs recovery draft/i)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /审计日志/i })).toBeInTheDocument();
    expect(await screen.findByText(/evaluation_task:task-recover-1/i)).toBeInTheDocument();
  });

  it("allows admins to revoke invitations and recover or close tasks", async () => {
    renderAdminApp();

    fireEvent.click(await screen.findByRole("button", { name: /撤销邀请 pending\.editor@example\.com/i }));
    await waitFor(() => {
      expect((mockedApi as any).revokeInvitation).toHaveBeenCalledWith("invite-1");
    });

    fireEvent.click(screen.getByRole("button", { name: /重试 task-recover-1/i }));
    await waitFor(() => {
      expect((mockedApi as any).retryAdminTask).toHaveBeenCalledWith("task-recover-1");
    });

    fireEvent.click(screen.getByRole("button", { name: /关闭 task-recover-1/i }));
    await waitFor(() => {
      expect((mockedApi as any).closeAdminTask).toHaveBeenCalledWith("task-recover-1");
    });
  });

  it("supports compact audit-log filtering in admin dashboard", async () => {
    renderAdminApp();

    const auditSection = screen.getByRole("heading", { name: /审计日志/i }).closest("section");
    expect(auditSection).not.toBeNull();
    const auditScoped = within(auditSection as HTMLElement);
    expect(await auditScoped.findByText(/evaluation_task:task-recover-1/i)).toBeInTheDocument();
    expect(auditScoped.getByText(/evaluation_task:task-recover-2/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/操作筛选/i), {
      target: { value: "close_task" },
    });
    fireEvent.click(screen.getByRole("button", { name: /筛选日志/i }));

    await waitFor(() => {
      expect((mockedApi as any).listAuditLogs).toHaveBeenLastCalledWith({
        action: "close_task",
      });
    });
    expect(auditScoped.queryByText(/evaluation_task:task-recover-1/i)).not.toBeInTheDocument();
    expect(await auditScoped.findByText(/evaluation_task:task-recover-2/i)).toBeInTheDocument();
  });

  it("keeps successful admin panels visible when one data source fails", async () => {
    mockedApi.getRecoveryTasks.mockRejectedValueOnce(new Error("task source unavailable"));
    mockedApi.listUsers.mockResolvedValueOnce([
      {
        id: "user-active",
        email: "active@example.com",
        role: "editor",
        display_name: "Active User",
        is_active: true,
      },
    ]);

    renderAdminApp();

    expect(await screen.findByRole("button", { name: /撤销邀请 pending\.editor@example\.com/i })).toBeInTheDocument();
    expect(await screen.findByText(/evaluation_task:task-recover-1/i)).toBeInTheDocument();
    expect(await screen.findByText(/active user - 编辑（启用）/i)).toBeInTheDocument();
    expect(await screen.findByText(/部分数据加载失败/i)).toBeInTheDocument();
  });

  it("keeps degraded-refresh warning after a successful admin action", async () => {
    mockedApi.getRecoveryTasks.mockRejectedValue(new Error("task source unavailable"));

    renderAdminApp();

    expect(await screen.findByText(/部分数据加载失败/i)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: /撤销邀请 pending\.editor@example\.com/i }));

    await waitFor(() => {
      expect((mockedApi as any).revokeInvitation).toHaveBeenCalledWith("invite-1");
    });
    expect(screen.getByText(/已撤销邀请：pending\.editor@example\.com/i)).toBeInTheDocument();
    expect(screen.getByText(/部分数据加载失败/i)).toBeInTheDocument();
  });

  it("shows an activation handoff link after creating an invitation", async () => {
    (mockedApi as any).createInvitation.mockResolvedValueOnce({
      id: "invite-new",
      email: "handoff@example.com",
      role: "editor",
      token: "handoff-token-123",
      expires_at: "2026-04-25T08:00:00Z",
    });

    renderAdminApp();

    fireEvent.change(screen.getByLabelText(/邀请邮箱/i), {
      target: { value: "handoff@example.com" },
    });
    fireEvent.change(screen.getByLabelText(/^角色$/i), {
      target: { value: "editor" },
    });
    fireEvent.click(screen.getByRole("button", { name: /创建邀请/i }));

    const linkInput = (await screen.findByLabelText(/激活链接/i)) as HTMLInputElement;
    expect(linkInput.value).toContain("invitation_token=handoff-token-123");
    expect(screen.getByText(/请将此链接发送给受邀用户/i)).toBeInTheDocument();
  });

  it("shows an expert review workspace and submits real dimension review data", async () => {
    renderExpertApp();

    expect(screen.getByText(/专家工作台/i)).toBeInTheDocument();
    expect(
      await screen.findByRole("button", { name: /打开 platform governance study/i })
    ).toBeInTheDocument();
    expect(await screen.findByLabelText(/问题创新性 专家评分/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/问题创新性 专家评分/i), {
      target: { value: "86.5" },
    });
    fireEvent.change(screen.getByLabelText(/问题创新性 修改理由/i), {
      target: { value: "问题意识更强，值得上调。" },
    });
    fireEvent.change(screen.getByLabelText(/理论建构力 专家评分/i), {
      target: { value: "78.25" },
    });
    fireEvent.change(screen.getByLabelText(/理论建构力 修改理由/i), {
      target: { value: "框架完整，但仍有推演空间。" },
    });

    fireEvent.click(screen.getByRole("button", { name: /提交复核/i }));

    await waitFor(() => {
      expect(mockedApi.submitReview).toHaveBeenCalledWith("review-1", [
        {
          dimension_key: "problem_originality",
          ai_score: 84,
          expert_score: 86.5,
          reason: "问题意识更强，值得上调。",
        },
        {
          dimension_key: "analytical_framework",
          ai_score: 80,
          expert_score: 78.25,
          reason: "框架完整，但仍有推演空间。",
        },
      ]);
    });
  });

  it("renders rich internal report details in expert workspace", async () => {
    renderExpertApp();

    expect(
      await screen.findByRole("button", { name: /打开 platform governance study/i })
    ).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /维度雷达图/i })).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { name: /模型评分/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: /证据摘录/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: /AI 分析/i }).length).toBeGreaterThan(0);
    expect(screen.getByText(/复核提交 review-internal-1/i)).toBeInTheDocument();
    expect(screen.getByText(/复核提交 review-internal-2/i)).toBeInTheDocument();
    expect(screen.getAllByText(/理论结构完整，但核心概念边界需要进一步明确/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/问题识别到位，但政策场景覆盖还可更完整/i).length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/问题创新性 专家评分/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/问题创新性 修改理由/i)).toBeInTheDocument();
  });

  it("blocks expert submission until every dimension reason is filled", async () => {
    renderExpertApp();

    expect(await screen.findByLabelText(/问题创新性 修改理由/i)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText(/问题创新性 修改理由/i), {
      target: { value: "只填写一个维度理由。" },
    });
    fireEvent.click(screen.getByRole("button", { name: /提交复核/i }));

    expect(await screen.findByText(/请补全所有维度的专家评分与修改理由/i)).toBeInTheDocument();
    expect(mockedApi.submitReview).not.toHaveBeenCalled();
  });
});
