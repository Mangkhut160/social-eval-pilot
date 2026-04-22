import { FormEvent, useEffect, useRef, useState } from "react";

import {
  acceptInvitation,
  assignExpert,
  closeAdminTask,
  createInvitation,
  deletePaper,
  getCurrentUser,
  getRecoveryTasks,
  listAuditLogs,
  listInvitations,
  getInternalReport,
  getPaperOptions,
  getPaperStatus,
  getPublicReport,
  getReportExportUrl,
  getReviewQueue,
  listExperts,
  listMyReviews,
  listPapers,
  listReportHistory,
  listUsers,
  login,
  retryAdminTask,
  revokeInvitation,
  logout,
  startPaperEvaluation,
  submitReview,
  uploadPaper,
} from "./lib/api";
import type {
  AuditLogItem,
  InvitationListItem,
  PaperOptions,
  PaperListItem,
  PaperStatus,
  RecoveryTask,
  ReportDimension,
  ReportHistoryItem,
  ReportSnapshot,
  ReviewQueueItem,
  ReviewSubmissionComment,
  ReviewTask,
  User,
} from "./lib/types";
import "./styles.css";

type AppProps = {
  initialUser?: User | null;
};

const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".txt"];
const SCORE_FORMATTER = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});
const ROLE_LABELS: Record<User["role"], string> = {
  submitter: "投稿者",
  editor: "编辑",
  expert: "专家",
  admin: "管理员",
};
const DISPLAY_NAME_TRANSLATIONS: Record<string, string> = {
  Submitter: "投稿者",
  Editor: "编辑",
  Expert: "专家",
  Admin: "管理员",
  "Initial Admin": "初始管理员",
};
const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  queued: "排队中",
  running: "评测中",
  completed: "已完成",
  failed: "失败",
  assigned: "已分配",
  submitted: "已提交",
  draft: "草稿",
};

function normalizeError(error: unknown): string {
  return error instanceof Error ? error.message : "发生了未知错误。";
}

function getPaperDisplayName(paper: PaperListItem): string {
  return paper.title?.trim() || paper.original_filename;
}

function formatRoleLabel(role: User["role"]): string {
  return ROLE_LABELS[role] ?? role;
}

function formatStatusLabel(status?: string | null): string {
  if (!status) {
    return "待处理";
  }
  return STATUS_LABELS[status] ?? status;
}

function formatSubmitterStatusLabel({
  paperStatus,
  taskStatus,
  precheckStatus,
  failureStage,
}: {
  paperStatus?: string | null;
  taskStatus?: string | null;
  precheckStatus?: string | null;
  failureStage?: string | null;
}): string {
  if (
    isPrecheckRejected(precheckStatus) ||
    failureStage === "ingestion" ||
    failureStage === "precheck" ||
    taskStatus === "failed"
  ) {
    return "需重新上传";
  }
  if (isPrecheckFlagged(precheckStatus) && taskStatus === "completed") {
    return "待人工复核";
  }

  const status = taskStatus ?? paperStatus;
  if (status === "processing" || status === "running" || status === "reviewing") {
    return "评审中";
  }
  return formatStatusLabel(status);
}

function formatUserIdentity(user: User): string {
  const display = user.display_name ?? user.email;
  return `当前用户：${DISPLAY_NAME_TRANSLATIONS[display] ?? display}`;
}

function formatUserDisplayName(user: Pick<User, "display_name" | "email">): string {
  return user.display_name?.trim() || user.email;
}

function formatRoundsLabel(rounds: number): string {
  return `${rounds} 轮`;
}

function formatScore(value?: number | null): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "待生成";
  }
  return SCORE_FORMATTER.format(value);
}

function formatDateTime(value?: string): string {
  if (!value) {
    return "待生成";
  }
  const timestamp = new Date(value);
  if (Number.isNaN(timestamp.getTime())) {
    return value;
  }
  return timestamp.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatHistoryLabel(item: ReportHistoryItem): string {
  return `版本 ${item.version}（${item.is_current ? "当前" : "历史"}）`;
}

function isPrecheckRejected(precheckStatus?: string | null): boolean {
  return precheckStatus === "reject";
}

function isPrecheckFlagged(precheckStatus?: string | null): boolean {
  return precheckStatus === "conditional_pass";
}

function formatWeightedTotalDisplay(
  weightedTotal?: number | null,
  precheckStatus?: string | null
): string {
  if (isPrecheckRejected(precheckStatus)) {
    return "预检拒稿";
  }
  if (weightedTotal === null || weightedTotal === undefined) {
    return "待生成";
  }
  return `${formatScore(weightedTotal)}/100`;
}

function summarizeConfidence(status: PaperStatus | null): string {
  if (isPrecheckRejected(status?.precheck_status)) {
    return "预检未通过";
  }
  if (isPrecheckFlagged(status?.precheck_status)) {
    const reliability = status?.reliability_summary;
    if (!reliability) {
      return "带风险通过，待人工复核";
    }
    if (reliability.low_confidence_count > 0) {
      return `预检带风险，另有 ${reliability.low_confidence_count} 个维度待复核`;
    }
    return "带风险通过，待人工复核";
  }
  const reliability = status?.reliability_summary;
  if (!reliability) {
    return "置信度待生成";
  }
  if (reliability.overall_high_confidence) {
    return "高置信度";
  }
  return `${reliability.low_confidence_count} 个维度待复核`;
}

function isAcceptedFile(file: File): boolean {
  const lowerName = file.name.toLowerCase();
  return ACCEPTED_EXTENSIONS.some((extension) => lowerName.endsWith(extension));
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

type ExpertReviewDraft = Record<
  string,
  {
    expertScore: string;
    reason: string;
  }
>;

function readInvitationTokenFromLocation(): string | null {
  if (typeof window === "undefined") {
    return null;
  }
  const params = new URLSearchParams(window.location.search);
  return params.get("invitation_token");
}

function clearInvitationTokenFromLocation(): void {
  if (typeof window === "undefined") {
    return;
  }
  window.history.replaceState({}, "", window.location.pathname);
}

function buildInvitationActivationUrl(token: string): string {
  if (typeof window !== "undefined" && window.location.origin) {
    return `${window.location.origin}/?invitation_token=${encodeURIComponent(token)}`;
  }
  return `/?invitation_token=${encodeURIComponent(token)}`;
}

function getSubmitterHistoryEmptyState(
  selectedPaper: PaperListItem | null,
  status: PaperStatus | null
): string {
  if (!selectedPaper) {
    return "请先上传稿件，或从左侧选择一篇稿件。";
  }
  if (isPrecheckRejected(status?.precheck_status ?? selectedPaper.precheck_status)) {
    return "该稿件未通过预检，请根据下列问题修改稿件后重新上传，再重新开始评测。";
  }

  const currentStatus = status?.task_status ?? selectedPaper.paper_status;
  if (currentStatus === "pending") {
    return "该稿件已上传。请先点击“开始评测”，系统才会生成首个报告快照。";
  }
  if (
    currentStatus === "queued" ||
    currentStatus === "processing" ||
    currentStatus === "running" ||
    currentStatus === "reviewing"
  ) {
    return "评测已启动，报告生成后会自动出现在这里。";
  }
  if (currentStatus === "failed") {
    return "本次评测未成功完成，请检查稿件后重新上传。";
  }
  return "暂时还没有报告快照，请稍后刷新。";
}

function getSubmitterReportEmptyState(
  selectedPaper: PaperListItem | null,
  status: PaperStatus | null
): string {
  if (!selectedPaper) {
    return "生成报告快照后，这里会显示报告内容。";
  }
  if (isPrecheckRejected(status?.precheck_status ?? selectedPaper.precheck_status)) {
    return "该稿件未通过预检，请根据下列问题修改后重新上传。";
  }

  const currentStatus = status?.task_status ?? selectedPaper.paper_status;
  if (currentStatus === "pending") {
    return "公开报告将在你点击“开始评测”并生成首个快照后显示在这里。";
  }
  if (
    currentStatus === "queued" ||
    currentStatus === "processing" ||
    currentStatus === "running" ||
    currentStatus === "reviewing"
  ) {
    return "评审进行中，公开报告生成后会显示在这里。";
  }
  if (currentStatus === "failed") {
    return "公开报告生成失败，请重新上传稿件后再次发起评测。";
  }
  return "生成报告快照后，这里会显示报告内容。";
}

function createExpertReviewDraft(dimensions: ReportDimension[]): ExpertReviewDraft {
  return Object.fromEntries(
    dimensions.map((dimension) => [
      dimension.key,
      {
        expertScore: "",
        reason: "",
      },
    ])
  );
}

function LoginForm({
  onLoggedIn,
  initialEmail = "submitter@example.com",
  notice = null,
}: {
  onLoggedIn: (user: User) => void;
  initialEmail?: string;
  notice?: string | null;
}) {
  const [email, setEmail] = useState(initialEmail);
  const [password, setPassword] = useState("secret123");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setEmail(initialEmail);
  }, [initialEmail]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const user = await login(email, password);
      setError(null);
      onLoggedIn(user);
    } catch (err) {
      setError(normalizeError(err));
    }
  };

  return (
    <section className="panel auth-card">
      <p className="eyebrow">试点评测入口</p>
      <h1>文科论文评价系统 登录</h1>
      <form className="stack" onSubmit={handleSubmit}>
        <label>
          邮箱
          <input value={email} onChange={(event) => setEmail(event.target.value)} />
        </label>
        <label>
          密码
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button type="submit">登录</button>
        {notice ? <p className="notice success">{notice}</p> : null}
        {error ? <p className="error">{error}</p> : null}
      </form>
    </section>
  );
}

function InvitationAcceptanceForm({
  token,
  onAccepted,
  onBackToLogin,
}: {
  token: string;
  onAccepted: (user: User) => void;
  onBackToLogin: () => void;
}) {
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    try {
      const user = await acceptInvitation({
        token,
        displayName,
        password,
      });
      setError(null);
      onAccepted(user);
    } catch (err) {
      setError(normalizeError(err));
    }
  };

  return (
    <section className="panel auth-card">
      <p className="eyebrow">邀请激活</p>
      <h1>激活账号</h1>
      <form className="stack" onSubmit={handleSubmit}>
        <label>
          显示名称
          <input value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
        </label>
        <label>
          密码
          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </label>
        <button type="submit">完成激活</button>
        <button type="button" className="secondary-button" onClick={onBackToLogin}>
          返回登录
        </button>
        {error ? <p className="error">{error}</p> : null}
      </form>
    </section>
  );
}

function ResultDimensionCard({ dimension }: { dimension: ReportDimension }) {
  const modelScores = Object.entries(dimension.ai.model_scores ?? {});
  const evidenceQuotes = dimension.ai.evidence_quotes ?? [];
  const analyses = dimension.ai.analysis ?? [];

  return (
    <article className="dimension-card">
      <div className="dimension-card-header">
        <div>
          <p className="eyebrow">评测维度</p>
          <h4>{dimension.name_zh}</h4>
          {dimension.name_en ? <p className="muted">{dimension.name_en}</p> : null}
        </div>
        <span className={`confidence-pill ${dimension.ai.is_high_confidence ? "ok" : "warn"}`}>
          {dimension.ai.is_high_confidence ? "高置信度" : "需要复核"}
        </span>
      </div>
      <div className="dimension-score-row">
        <strong>{formatScore(dimension.ai.mean_score)}</strong>
        <span>标准差 {formatScore(dimension.ai.std_score)}</span>
      </div>

      {modelScores.length > 0 ? (
        <section className="dimension-detail-section">
          <h5>模型评分</h5>
          <ul className="dimension-meta-list">
            {modelScores.map(([modelName, score]) => (
              <li key={modelName}>
                <span>{modelName}</span>
                <strong>{formatScore(score)}</strong>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {evidenceQuotes.length > 0 ? (
        <section className="dimension-detail-section">
          <h5>证据摘录</h5>
          <ul className="list dimension-quote-list">
            {evidenceQuotes.map((quote, index) => (
              <li key={`${dimension.key}-quote-${index}`}>{quote}</li>
            ))}
          </ul>
        </section>
      ) : null}

      {analyses.length > 0 ? (
        <section className="dimension-detail-section">
          <h5>AI 分析</h5>
          <ul className="list dimension-analysis-list">
            {analyses.map((analysis, index) => (
              <li key={`${dimension.key}-analysis-${index}`}>{analysis}</li>
            ))}
          </ul>
        </section>
      ) : null}
    </article>
  );
}

function getRadarChartImageSrc(imageBase64: string): string {
  if (imageBase64.startsWith("data:")) {
    return imageBase64;
  }
  return `data:image/png;base64,${imageBase64}`;
}

function getRadarChartDisplayLabels(report: ReportSnapshot): string[] {
  const dimensionLabelMap = new Map<string, string>();
  for (const dimension of report.dimensions) {
    const zhLabel = dimension.name_zh?.trim();
    if (!zhLabel) {
      continue;
    }
    dimensionLabelMap.set(zhLabel, zhLabel);
    const enLabel = dimension.name_en?.trim();
    if (enLabel) {
      dimensionLabelMap.set(enLabel, zhLabel);
    }
  }

  const chartLabels = report.radar_chart?.labels
    ?.map((label) => dimensionLabelMap.get(label) ?? label)
    .filter((label): label is string => Boolean(label?.trim()));

  if (chartLabels && chartLabels.length > 0) {
    return chartLabels;
  }

  const labelsFromDimensions = report.dimensions
    .map((dimension) => dimension.name_zh?.trim())
    .filter((label): label is string => Boolean(label));
  if (labelsFromDimensions.length > 0) {
    return labelsFromDimensions;
  }

  return [];
}

function ReportRadarChart({ report }: { report: ReportSnapshot }) {
  const imageBase64 = report.radar_chart?.image_base64;
  const displayLabels = getRadarChartDisplayLabels(report);

  if (!imageBase64) {
    return null;
  }

  return (
    <section className="report-detail-section report-radar-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">维度结构</p>
          <h4>维度雷达图</h4>
        </div>
      </div>
      <img
        className="report-radar-image"
        alt="维度雷达图"
        src={getRadarChartImageSrc(imageBase64)}
      />
      {displayLabels.length > 0 ? (
        <p className="report-radar-summary">维度：{displayLabels.join("、")}</p>
      ) : null}
    </section>
  );
}

function ReportAiOverview({ report }: { report: ReportSnapshot }) {
  const analysisItems = report.dimensions.flatMap((dimension) =>
    (dimension.ai.analysis ?? []).map((analysis, index) => ({
      key: `${dimension.key}-analysis-overview-${index}`,
      label: dimension.name_zh,
      text: analysis,
    }))
  );
  const evidenceItems = report.dimensions.flatMap((dimension) =>
    (dimension.ai.evidence_quotes ?? []).map((quote, index) => ({
      key: `${dimension.key}-evidence-overview-${index}`,
      label: dimension.name_zh,
      text: quote,
    }))
  );

  if (analysisItems.length === 0 && evidenceItems.length === 0) {
    return null;
  }

  const highConfidenceCount = report.dimensions.filter(
    (dimension) => dimension.ai.is_high_confidence
  ).length;
  const lowConfidenceCount = report.dimensions.length - highConfidenceCount;

  return (
    <section className="report-detail-section report-overview-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">AI 总评</p>
          <h4>AI 总体评价</h4>
        </div>
      </div>
      <p className="report-overview-lead">
        {`AI 已完成 ${report.dimensions.length} 个维度的评估，当前综合得分为 ${formatWeightedTotalDisplay(
          report.weighted_total,
          report.precheck_status
        )}。`}
      </p>
      <div className="report-summary">
        <div>
          <span>高置信度维度</span>
          <strong>{highConfidenceCount}</strong>
        </div>
        <div>
          <span>需复核维度</span>
          <strong>{lowConfidenceCount}</strong>
        </div>
        <div>
          <span>AI 结论条目</span>
          <strong>{analysisItems.length}</strong>
        </div>
        <div>
          <span>关键依据条目</span>
          <strong>{evidenceItems.length}</strong>
        </div>
      </div>

      {analysisItems.length > 0 ? (
        <section className="dimension-detail-section">
          <h5>AI 主要结论</h5>
          <ul className="list dimension-analysis-list">
            {analysisItems.map((item) => (
              <li key={item.key}>
                <strong>{item.label}：</strong>
                {item.text}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {evidenceItems.length > 0 ? (
        <section className="dimension-detail-section">
          <h5>AI 关键输出</h5>
          <ul className="list dimension-quote-list">
            {evidenceItems.map((item) => (
              <li key={item.key}>
                <strong>{item.label}：</strong>
                {item.text}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </section>
  );
}

function ExpertReviewCommentsSection({ report }: { report: ReportSnapshot }) {
  const dimensionNameByKey = new Map(
    report.dimensions.map((dimension) => [dimension.key, dimension.name_zh])
  );
  const reviewGroups = report.expert_reviews
    .map((review) => ({
      reviewId: review.review_id,
      reviewStatus: review.status,
      comments: review.comments.map((comment, index) => ({
        ...comment,
        key: `${review.review_id}-${comment.dimension_key}-${index}`,
        dimensionName: dimensionNameByKey.get(comment.dimension_key) ?? comment.dimension_key,
      })),
    }))
    .filter((group) => group.comments.length > 0);
  const totalCommentCount = reviewGroups.reduce(
    (sum, group) => sum + group.comments.length,
    0
  );

  if (totalCommentCount === 0) {
    return null;
  }

  return (
    <section className="report-detail-section">
      <div className="section-heading">
        <div>
          <p className="eyebrow">人工复核</p>
          <h4>专家复核意见</h4>
        </div>
        <span className="count-chip">{totalCommentCount}</span>
      </div>
      <div className="expert-review-group-list">
        {reviewGroups.map((group) => (
          <section className="expert-review-group" key={group.reviewId}>
            <div className="expert-review-group-header">
              <h5>{`复核提交 ${group.reviewId}`}</h5>
              <span className="count-chip">{formatStatusLabel(group.reviewStatus)}</span>
            </div>
            <div className="expert-comment-list expert-review-comment-list">
              {group.comments.map((comment) => (
                <article key={comment.key} className="expert-comment-card">
                  <p className="expert-comment-meta">
                    <strong>{comment.dimensionName}</strong>
                    <span>专家评分 {formatScore(comment.expert_score)}</span>
                  </p>
                  <p>{comment.reason}</p>
                </article>
              ))}
            </div>
          </section>
        ))}
      </div>
    </section>
  );
}

function PrecheckRejectedSummary({ report }: { report: ReportSnapshot }) {
  const issues = report.precheck_result?.issues ?? [];
  const recommendation = report.precheck_result?.recommendation;

  return (
    <section className="precheck-summary">
      <div className="precheck-summary-header">
        <p className="eyebrow">质量门禁</p>
        <h4>预检未通过</h4>
      </div>
      <p className="muted">该稿件在预检阶段被拒稿，未进入维度评分。</p>
      <p className="notice info">请根据下列问题修改稿件后重新上传，再重新开始评测。</p>
      {issues.length > 0 ? (
        <ul className="list">
          {issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      ) : null}
      {recommendation ? (
        <p className="notice info">建议：{recommendation}</p>
      ) : null}
    </section>
  );
}

function PrecheckFlaggedSummary({ report }: { report: ReportSnapshot }) {
  const issues = report.precheck_result?.consensus?.issues ?? report.precheck_result?.issues ?? [];
  const recommendation =
    report.precheck_result?.consensus?.recommendation ?? report.precheck_result?.recommendation;
  const reviewFlags =
    report.precheck_result?.consensus?.review_flags ?? report.precheck_result?.review_flags ?? [];

  return (
    <section className="precheck-summary">
      <div className="precheck-summary-header">
        <p className="eyebrow">质量门禁</p>
        <h4>带风险进入评分</h4>
      </div>
      <p className="muted">该稿件已完成六维评分，但预检检测到需要人工复核的风险项。</p>
      <p className="notice info">建议结合下列问题和模型评分结果进行专家复核。</p>
      {issues.length > 0 ? (
        <ul className="list">
          {issues.map((issue) => (
            <li key={issue}>{issue}</li>
          ))}
        </ul>
      ) : null}
      {reviewFlags.length > 0 ? (
        <p className="notice info">复核标记：{reviewFlags.join("、")}</p>
      ) : null}
      {recommendation ? <p className="notice info">建议：{recommendation}</p> : null}
    </section>
  );
}

function SubmitterDashboard() {
  const [paperOptions, setPaperOptions] = useState<PaperOptions | null>(null);
  const [papers, setPapers] = useState<PaperListItem[]>([]);
  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [status, setStatus] = useState<PaperStatus | null>(null);
  const [reportHistory, setReportHistory] = useState<ReportHistoryItem[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [report, setReport] = useState<ReportSnapshot | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isDropActive, setIsDropActive] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [selectedModels, setSelectedModels] = useState<string[]>([]);
  const [evaluationRounds, setEvaluationRounds] = useState(1);
  const [isDeletingPaperId, setIsDeletingPaperId] = useState<string | null>(null);
  const [isStartingEvaluation, setIsStartingEvaluation] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const hasInitializedOptionsRef = useRef(false);

  async function refreshPapers(preferredPaperId?: string | null): Promise<void> {
    const nextPapers = await listPapers();
    setPapers(nextPapers);
    const availableIds = new Set(nextPapers.map((paper) => paper.paper_id));
    setSelectedPaperId((current) => {
      const preferred = preferredPaperId ?? current;
      if (preferred && availableIds.has(preferred)) {
        return preferred;
      }
      return nextPapers[0]?.paper_id ?? null;
    });
  }

  useEffect(() => {
    void refreshPapers().catch(() => {
      setPapers([]);
      setSelectedPaperId(null);
      setError("无法加载你的稿件列表。");
    });
  }, []);

  useEffect(() => {
    let cancelled = false;

    void getPaperOptions()
      .then((nextOptions) => {
        if (cancelled) {
          return;
        }
        setPaperOptions(nextOptions);
        if (!hasInitializedOptionsRef.current) {
          setSelectedModels(nextOptions.default_selected_models);
          setEvaluationRounds(nextOptions.default_rounds);
          hasInitializedOptionsRef.current = true;
        }
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setPaperOptions(null);
        setError("无法加载评测配置。");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedPaperId) {
      setStatus(null);
      setReportHistory([]);
      setSelectedVersion(null);
      setReport(null);
      return;
    }

    let cancelled = false;

    const loadPaperWorkspace = async (paperId: string) => {
      const nextStatus = await getPaperStatus(paperId);
      const nextHistory = await listReportHistory(paperId);
      if (cancelled) {
        return;
      }

      setStatus(nextStatus);
      setReportHistory(nextHistory);

      if (nextHistory.length === 0) {
        setSelectedVersion(null);
        setReport(null);
        return;
      }

      const currentHistoryItem =
        nextHistory.find((item) => item.is_current) ?? nextHistory[0];
      setSelectedVersion(currentHistoryItem.version);

      const nextReport = currentHistoryItem.is_current
        ? await getPublicReport(paperId)
        : await getPublicReport(paperId, currentHistoryItem.version);
      if (cancelled) {
        return;
      }
      setReport(nextReport);
    };

    void loadPaperWorkspace(selectedPaperId).catch((err) => {
      if (cancelled) {
        return;
      }
      setError(normalizeError(err));
      setStatus(null);
      setReportHistory([]);
      setSelectedVersion(null);
      setReport(null);
    });

    return () => {
      cancelled = true;
    };
  }, [selectedPaperId]);

  const selectedPaper =
    papers.find((paper) => paper.paper_id === selectedPaperId) ?? null;
  const selectedHistoryItem =
    reportHistory.find((item) => item.version === selectedVersion) ??
    reportHistory.find((item) => item.is_current) ??
    null;
  const activeEvaluationConfig = report?.evaluation_config ?? status?.evaluation_config ?? null;
  const currentPrecheckStatus = report?.precheck_status ?? status?.precheck_status ?? null;

  async function handleHistorySelect(item: ReportHistoryItem): Promise<void> {
    if (!selectedPaperId) {
      return;
    }
    try {
      setError(null);
      setSelectedVersion(item.version);
      const nextReport = item.is_current
        ? await getPublicReport(selectedPaperId)
        : await getPublicReport(selectedPaperId, item.version);
      setReport(nextReport);
    } catch (err) {
      setError(normalizeError(err));
    }
  }

  async function handleFileUpload(file: File): Promise<void> {
    if (!isAcceptedFile(file)) {
      setError("试点环境仅支持 PDF、DOCX 和 TXT 文件。");
      return;
    }
    if (!paperOptions) {
      setError("评测配置仍在加载中。");
      return;
    }
    if (selectedModels.length === 0) {
      setError("请至少选择一个评测模型后再上传。");
      return;
    }
    if (
      evaluationRounds < paperOptions.min_rounds ||
      evaluationRounds > paperOptions.max_rounds
    ) {
      setError(`评测轮数必须在 ${paperOptions.min_rounds} 到 ${paperOptions.max_rounds} 之间。`);
      return;
    }

    try {
      setError(null);
      setMessage(null);
      setIsUploading(true);
      const payload = await uploadPaper(file, {
        selectedModels,
        evaluationRounds,
      });
      setMessage(`已上传 ${file.name}。选中该稿件后，点击“开始评测”即可。`);
      await refreshPapers(payload.paper_id);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setIsUploading(false);
      setIsDropActive(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  }

  const handleFileSelection = async (event: FormEvent<HTMLInputElement>) => {
    const file = event.currentTarget.files?.[0];
    if (file) {
      await handleFileUpload(file);
    }
  };

  function handleModelToggle(modelName: string): void {
    setSelectedModels((current) => {
      if (current.includes(modelName)) {
        setError(null);
        return current.filter((item) => item !== modelName);
      }
      if (paperOptions && current.length >= paperOptions.max_selected_models) {
        setError(`试点环境最多可选择 ${paperOptions.max_selected_models} 个模型。`);
        return current;
      }
      setError(null);
      return [...current, modelName];
    });
  }

  function handleRoundsChange(event: FormEvent<HTMLInputElement>): void {
    const rawValue = Number(event.currentTarget.value);
    if (Number.isNaN(rawValue)) {
      return;
    }
    if (!paperOptions) {
      setEvaluationRounds(rawValue);
      return;
    }
    setEvaluationRounds(
      clamp(rawValue, paperOptions.min_rounds, paperOptions.max_rounds)
    );
  }

  async function handleStartEvaluation(): Promise<void> {
    if (!selectedPaperId) {
      return;
    }

    try {
      setError(null);
      setMessage(null);
      setIsStartingEvaluation(true);
      const payload = await startPaperEvaluation(selectedPaperId);
      await refreshPapers(payload.paper_id);

      const nextStatus = await getPaperStatus(payload.paper_id);
      setStatus(nextStatus);

      const nextHistory = await listReportHistory(payload.paper_id);
      setReportHistory(nextHistory);

      if (nextHistory.length === 0) {
        setSelectedVersion(null);
        setReport(null);
        setMessage("评测已启动，稍后刷新该稿件即可查看结果。");
        return;
      }

      const currentHistoryItem =
        nextHistory.find((item) => item.is_current) ?? nextHistory[0];
      setSelectedVersion(currentHistoryItem.version);
      const nextReport = currentHistoryItem.is_current
        ? await getPublicReport(payload.paper_id)
        : await getPublicReport(payload.paper_id, currentHistoryItem.version);
      setReport(nextReport);
      setMessage("评测已完成，最新报告快照现已可查看。");
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setIsStartingEvaluation(false);
    }
  }

  async function handleDeletePaper(paper: PaperListItem): Promise<void> {
    try {
      setError(null);
      setMessage(null);
      setIsDeletingPaperId(paper.paper_id);
      await deletePaper(paper.paper_id);
      setMessage(`已从试点工作区删除《${getPaperDisplayName(paper)}》。`);
      await refreshPapers(selectedPaperId === paper.paper_id ? null : selectedPaperId);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setIsDeletingPaperId(null);
    }
  }

  return (
    <div className="submitter-layout">
      <aside className="submitter-sidebar">
        <section className="panel upload-panel">
          <p className="eyebrow">提交稿件</p>
          <h2>投稿工作台</h2>
          <section className="upload-config-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">评测模型</p>
                <h3>选择评测模型</h3>
              </div>
              <span className="count-chip">
                {paperOptions
                  ? `${selectedModels.length}/${paperOptions.max_selected_models}`
                  : "加载中"}
              </span>
            </div>

            {paperOptions ? (
              <>
                <div className="model-option-grid">
                  {paperOptions.model_options.map((option) => {
                    const isSelected = selectedModels.includes(option.name);
                    return (
                      <label
                        key={option.name}
                        className={`model-option ${isSelected ? "selected" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={isSelected}
                          onChange={() => handleModelToggle(option.name)}
                        />
                        <span>{option.label}</span>
                        <small>{`来源：${option.source}`}</small>
                      </label>
                    );
                  })}
                </div>
                <label className="rounds-field" htmlFor="evaluation-rounds">
                  <span>评测轮数</span>
                  <input
                    id="evaluation-rounds"
                    type="number"
                    min={paperOptions.min_rounds}
                    max={paperOptions.max_rounds}
                    value={evaluationRounds}
                    onChange={(event) => handleRoundsChange(event)}
                  />
                </label>
                <p className="muted">
                  最多选择 {paperOptions.max_selected_models} 个模型。轮数越高，结果越稳定，但耗时更长。
                </p>
              </>
            ) : (
              <p className="empty-state">正在加载评测配置...</p>
            )}
          </section>

          <div
            className={`dropzone ${isDropActive ? "active" : ""}`}
            data-testid="paper-dropzone"
            onDragEnter={(event) => {
              event.preventDefault();
              setIsDropActive(true);
            }}
            onDragLeave={(event) => {
              event.preventDefault();
              setIsDropActive(false);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              event.dataTransfer.dropEffect = "copy";
            }}
            onDrop={(event) => {
              event.preventDefault();
              setIsDropActive(false);
              const file = event.dataTransfer.files?.[0];
              if (file) {
                void handleFileUpload(file);
              }
            }}
          >
            <p className="dropzone-title">将稿件拖拽到这里</p>
            <p className="muted">支持格式：PDF、DOCX、TXT</p>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading || !paperOptions}
            >
              {isUploading ? "上传中..." : "选择文件"}
            </button>
            <input
              ref={fileInputRef}
              className="sr-only"
              type="file"
              accept={ACCEPTED_EXTENSIONS.join(",")}
              onInput={(event) => void handleFileSelection(event)}
            />
          </div>
          {message ? <p className="notice success">{message}</p> : null}
          {error ? <p className="notice error">{error}</p> : null}
        </section>

        <section className="panel paper-list-panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">最近稿件</p>
              <h3>我的稿件</h3>
            </div>
            <span className="count-chip">{papers.length}</span>
          </div>
          {papers.length === 0 ? (
            <p className="empty-state">还没有已上传稿件。</p>
          ) : (
            <div className="paper-list">
              {papers.map((paper) => (
                <div
                  key={paper.paper_id}
                  className={`paper-row-card ${
                    paper.paper_id === selectedPaperId ? "selected" : ""
                  }`}
                >
                  <button
                    type="button"
                    aria-label={`打开 ${getPaperDisplayName(paper)}`}
                    className={`paper-row ${paper.paper_id === selectedPaperId ? "selected" : ""}`}
                    onClick={() => setSelectedPaperId(paper.paper_id)}
                  >
                    <strong>{getPaperDisplayName(paper)}</strong>
                    <span>
                      {formatSubmitterStatusLabel({
                        paperStatus: paper.paper_status,
                        precheckStatus: paper.precheck_status,
                      })}
                    </span>
                  </button>
                  {paper.paper_status === "completed" ? (
                    <button
                      type="button"
                      className="delete-paper-button"
                      aria-label={`删除 ${getPaperDisplayName(paper)}`}
                      disabled={isDeletingPaperId === paper.paper_id}
                      onClick={() => void handleDeletePaper(paper)}
                    >
                      {isDeletingPaperId === paper.paper_id ? "删除中..." : "删除"}
                    </button>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </section>
      </aside>

      <main className="submitter-main">
        <section className="panel hero-panel">
          <div>
            <p className="eyebrow">当前稿件</p>
            <h2>{selectedPaper ? getPaperDisplayName(selectedPaper) : "选择一篇稿件查看详情"}</h2>
            <p className="muted">
              {selectedPaper
                ? `任务 ${status?.task_id ?? "待生成"} 当前状态：${formatSubmitterStatusLabel({
                    paperStatus: selectedPaper.paper_status,
                    taskStatus: status?.task_status ?? selectedPaper.paper_status,
                    precheckStatus: currentPrecheckStatus,
                    failureStage: status?.failure_stage,
                  })}。`
                : "请先上传稿件，或从左侧选择一篇稿件。"}
            </p>
          </div>
          {selectedPaperId && status?.task_status === "pending" ? (
            <button
              type="button"
              className="primary-action-button"
              onClick={() => void handleStartEvaluation()}
              disabled={isStartingEvaluation}
            >
              {isStartingEvaluation ? "启动中..." : "开始评测"}
            </button>
          ) : null}
          <div className="metric-grid">
            <div className="metric-card">
              <span>状态</span>
              <strong>
                {formatSubmitterStatusLabel({
                  paperStatus: status?.paper_status ?? selectedPaper?.paper_status,
                  taskStatus: status?.task_status,
                  precheckStatus: currentPrecheckStatus,
                  failureStage: status?.failure_stage,
                })}
              </strong>
            </div>
            <div className="metric-card">
              <span>置信度</span>
              <strong>{summarizeConfidence(status)}</strong>
            </div>
            <div className="metric-card">
              <span>综合得分</span>
              <strong>
                {formatWeightedTotalDisplay(report?.weighted_total, currentPrecheckStatus)}
              </strong>
            </div>
          </div>
          {activeEvaluationConfig ? (
            <div className="evaluation-config-banner">
              <div className="evaluation-config-copy">
                <span className="eyebrow">评测配置</span>
                <strong>{formatRoundsLabel(activeEvaluationConfig.evaluation_rounds)}</strong>
              </div>
              <div className="selected-model-list">
                {activeEvaluationConfig.selected_models.map((modelName) => (
                  <span className="model-chip" key={modelName}>
                    {modelName}
                  </span>
                ))}
              </div>
            </div>
          ) : null}
        </section>

        <section className="workspace-grid">
          <section className="panel history-panel">
            <div className="section-heading">
              <div>
                <p className="eyebrow">结果快照</p>
                <h3>报告历史</h3>
              </div>
            </div>
            {reportHistory.length === 0 ? (
              <p className="empty-state">{getSubmitterHistoryEmptyState(selectedPaper, status)}</p>
            ) : (
              <div className="history-list">
                {reportHistory.map((item) => (
                  <button
                    type="button"
                    key={item.report_id}
                    className={`history-row ${item.version === selectedVersion ? "selected" : ""}`}
                    onClick={() => void handleHistorySelect(item)}
                  >
                    <strong>{formatHistoryLabel(item)}</strong>
                    <span>
                      {formatWeightedTotalDisplay(
                        item.weighted_total,
                        item.version === selectedVersion
                          ? report?.precheck_status ?? item.precheck_status
                          : item.precheck_status
                      )}
                    </span>
                    <small>{formatDateTime(item.created_at)}</small>
                  </button>
                ))}
              </div>
            )}
          </section>

          <section className="panel report-panel">
            <div className="section-heading report-header">
              <div>
                <p className="eyebrow">可读结果</p>
                <h3>{report?.paper_title ?? "公开报告"}</h3>
              </div>
              {selectedPaperId && selectedHistoryItem ? (
                <div className="report-actions">
                  <span className="version-chip">版本 {selectedHistoryItem.version}</span>
                  <a
                    href={getReportExportUrl(
                      selectedPaperId,
                      "json",
                      "public",
                      selectedHistoryItem.is_current ? undefined : selectedHistoryItem.version
                    )}
                  >
                    下载 JSON
                  </a>
                  <a
                    href={getReportExportUrl(
                      selectedPaperId,
                      "pdf",
                      "public",
                      selectedHistoryItem.is_current ? undefined : selectedHistoryItem.version
                    )}
                  >
                    下载 PDF
                  </a>
                </div>
              ) : null}
            </div>

            {report ? (
              <>
                <div className="report-summary">
                  <div>
                    <span>版本</span>
                    <strong>{selectedHistoryItem?.version ?? "当前"}</strong>
                  </div>
                  <div>
                    <span>生成时间</span>
                    <strong>{formatDateTime(selectedHistoryItem?.created_at)}</strong>
                  </div>
                  <div>
                    <span>综合得分</span>
                    <strong>
                      {formatWeightedTotalDisplay(report.weighted_total, report.precheck_status)}
                    </strong>
                  </div>
                  <div>
                    <span>评测状态</span>
                    <strong>
                      {isPrecheckRejected(report.precheck_status)
                        ? "未进入维度评分"
                        : isPrecheckFlagged(report.precheck_status)
                          ? "已完成评分，待人工复核"
                          : formatRoundsLabel(report.evaluation_config?.evaluation_rounds ?? 1)}
                    </strong>
                  </div>
                </div>

                {report.expert_reviews.length > 0 ? (
                  <p className="notice info">
                    该快照附带 {report.expert_reviews.length} 条专家复核记录。
                  </p>
                ) : null}

                {isPrecheckRejected(report.precheck_status) ? (
                  <PrecheckRejectedSummary report={report} />
                ) : (
                  <>
                    {isPrecheckFlagged(report.precheck_status) ? (
                      <PrecheckFlaggedSummary report={report} />
                    ) : null}
                    <ReportAiOverview report={report} />
                    <ReportRadarChart report={report} />
                    <div className="dimension-grid">
                      {report.dimensions.map((dimension) => (
                        <ResultDimensionCard key={dimension.key} dimension={dimension} />
                      ))}
                    </div>
                    <ExpertReviewCommentsSection report={report} />
                  </>
                )}

                <details className="raw-json-panel">
                  <summary>原始报告 JSON</summary>
                  <pre>{JSON.stringify(report, null, 2)}</pre>
                </details>
              </>
            ) : (
              <p className="empty-state">{getSubmitterReportEmptyState(selectedPaper, status)}</p>
            )}
          </section>
        </section>
      </main>
    </div>
  );
}

function EditorDashboard() {
  const [queue, setQueue] = useState<ReviewQueueItem[]>([]);
  const [experts, setExperts] = useState<User[]>([]);
  const [selectedTaskId, setSelectedTaskId] = useState<string | null>(null);
  const [selectedExpertIds, setSelectedExpertIds] = useState<string[]>([]);
  const [report, setReport] = useState<ReportSnapshot | null>(null);
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isAssigning, setIsAssigning] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async (preferredTaskId?: string | null) => {
    const [queueItems, expertItems] = await Promise.all([getReviewQueue(), listExperts()]);
    setQueue(queueItems);
    setExperts(expertItems);
    const queueTaskIds = new Set(queueItems.map((item) => item.task_id));
    setSelectedTaskId((current) => {
      const nextTarget = preferredTaskId ?? current;
      if (nextTarget && queueTaskIds.has(nextTarget)) {
        return nextTarget;
      }
      return queueItems[0]?.task_id ?? null;
    });
  };

  useEffect(() => {
    void refresh().catch(() => {
      setQueue([]);
      setExperts([]);
      setSelectedTaskId(null);
      setError("无法加载编辑工作台数据。");
    });
  }, []);

  const selectedQueueItem = queue.find((item) => item.task_id === selectedTaskId) ?? null;

  useEffect(() => {
    if (!selectedQueueItem) {
      setReport(null);
      return;
    }

    let cancelled = false;
    setIsLoadingReport(true);
    setError(null);

    void getInternalReport(selectedQueueItem.paper_id)
      .then((nextReport) => {
        if (!cancelled) {
          setReport(nextReport);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setReport(null);
          setError(normalizeError(err));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingReport(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedQueueItem]);

  function toggleExpertSelection(expertId: string): void {
    setSelectedExpertIds((current) =>
      current.includes(expertId)
        ? current.filter((item) => item !== expertId)
        : [...current, expertId]
    );
  }

  async function handleAssignExperts(): Promise<void> {
    if (!selectedQueueItem) {
      setError("请先从左侧选择一条复核任务。");
      return;
    }
    if (selectedExpertIds.length === 0) {
      setError("请至少选择一位专家后再分配。");
      return;
    }

    try {
      setError(null);
      setMessage(null);
      setIsAssigning(true);
      await assignExpert(selectedQueueItem.task_id, selectedExpertIds);
      setMessage(`已为当前任务分配 ${selectedExpertIds.length} 位专家。`);
      setSelectedExpertIds([]);
      await refresh(selectedQueueItem.task_id);
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setIsAssigning(false);
    }
  }

  return (
    <div className="editor-layout">
      <section className="panel editor-sidebar">
        <h2>编辑工作台</h2>
        <p className="muted">选择待复核任务后，可查看内部报告并把任务分配给专家。</p>
        {queue.length === 0 ? (
          <p className="empty-state">暂无待分配任务。</p>
        ) : (
          <div className="paper-list">
            {queue.map((item) => {
              const itemLabel = item.paper_title ?? item.paper_id;
              return (
                <button
                  type="button"
                  key={item.task_id}
                  aria-label={`打开 ${itemLabel}`}
                  className={`paper-row ${item.task_id === selectedTaskId ? "selected" : ""}`}
                  onClick={() => setSelectedTaskId(item.task_id)}
                >
                  <strong>{itemLabel}</strong>
                  <span>{formatStatusLabel(item.task_status)}</span>
                  <small className="muted">
                    {item.needs_assignment
                      ? "待分配专家"
                      : `已分配 ${item.assigned_reviews.length} 位专家`}
                  </small>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="panel editor-main">
        <div className="section-heading">
          <div>
            <p className="eyebrow">任务详情</p>
            <h3>
              {selectedQueueItem?.paper_title ?? selectedQueueItem?.paper_id ?? "选择一条复核任务"}
            </h3>
          </div>
          {selectedQueueItem ? (
            <span className="count-chip">{formatStatusLabel(selectedQueueItem.task_status)}</span>
          ) : null}
        </div>
        {message ? <p className="notice success">{message}</p> : null}
        {error ? <p className="notice error">{error}</p> : null}
        {!selectedQueueItem ? (
          <p className="empty-state">请先从左侧选择一条复核任务。</p>
        ) : isLoadingReport ? (
          <p className="empty-state">正在加载内部报告...</p>
        ) : report ? (
          <>
            <div className="report-summary">
              <div>
                <span>任务编号</span>
                <strong>{selectedQueueItem.task_id}</strong>
              </div>
              <div>
                <span>稿件状态</span>
                <strong>{formatStatusLabel(selectedQueueItem.paper_status)}</strong>
              </div>
              <div>
                <span>综合得分</span>
                <strong>
                  {formatWeightedTotalDisplay(report.weighted_total, report.precheck_status)}
                </strong>
              </div>
              <div>
                <span>评测轮数</span>
                <strong>{formatRoundsLabel(report.evaluation_config?.evaluation_rounds ?? 1)}</strong>
              </div>
            </div>

            <p className="notice info">
              待复核维度：
              {selectedQueueItem.low_confidence_dimensions.length > 0
                ? selectedQueueItem.low_confidence_dimensions.join("、")
                : "当前任务未标记低置信度维度"}
            </p>

            {selectedQueueItem.assigned_reviews.length > 0 ? (
              <section className="editor-assignment-summary">
                <div className="section-heading">
                  <div>
                    <p className="eyebrow">已分配专家</p>
                    <h4>当前分配情况</h4>
                  </div>
                </div>
                <div className="history-list">
                  {selectedQueueItem.assigned_reviews.map((assignedReview) => (
                    <div className="history-row" key={assignedReview.review_id}>
                      <strong>
                        {assignedReview.expert_display_name ?? assignedReview.expert_email}
                      </strong>
                      <span>{assignedReview.expert_email}</span>
                      <small>{formatStatusLabel(assignedReview.status)}</small>
                    </div>
                  ))}
                </div>
              </section>
            ) : (
              <p className="empty-state">当前任务尚未分配专家。</p>
            )}

            {report.precheck_status === "reject" ? (
              <PrecheckRejectedSummary report={report} />
            ) : (
              <>
                {isPrecheckFlagged(report.precheck_status) ? (
                  <PrecheckFlaggedSummary report={report} />
                ) : null}
                <ReportAiOverview report={report} />
                <ReportRadarChart report={report} />
                <div className="dimension-grid">
                  {report.dimensions.map((dimension) => (
                    <ResultDimensionCard key={dimension.key} dimension={dimension} />
                  ))}
                </div>
                <ExpertReviewCommentsSection report={report} />
              </>
            )}
          </>
        ) : (
          <p className="empty-state">内部报告暂时不可用，请稍后重试。</p>
        )}
      </section>

      <section className="panel editor-assignment-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">专家分配</p>
            <h3>选择专家</h3>
          </div>
          <span className="count-chip">{selectedExpertIds.length}</span>
        </div>
        {experts.length === 0 ? (
          <p className="empty-state">当前没有可分配专家。</p>
        ) : (
          <div className="model-option-grid">
            {experts.map((expert) => {
              const selected = selectedExpertIds.includes(expert.id);
              return (
                <label
                  key={expert.id}
                  className={`model-option ${selected ? "selected" : ""}`}
                >
                  <input
                    aria-label={formatUserDisplayName(expert)}
                    type="checkbox"
                    checked={selected}
                    onChange={() => toggleExpertSelection(expert.id)}
                  />
                  <span>{formatUserDisplayName(expert)}</span>
                  <small>{expert.email}</small>
                </label>
              );
            })}
          </div>
        )}
        <button
          type="button"
          className="primary-action-button"
          disabled={isAssigning || !selectedQueueItem}
          onClick={() => void handleAssignExperts()}
        >
          {isAssigning ? "分配中..." : "分配专家"}
        </button>
        <p className="muted">支持为同一任务同时分配多位专家，以便并行复核。</p>
      </section>
    </div>
  );
}

function ExpertDashboard() {
  const [reviews, setReviews] = useState<ReviewTask[]>([]);
  const [selectedReviewId, setSelectedReviewId] = useState<string | null>(null);
  const [report, setReport] = useState<ReportSnapshot | null>(null);
  const [draft, setDraft] = useState<ExpertReviewDraft>({});
  const [isLoadingReport, setIsLoadingReport] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const refresh = async () => {
    const nextReviews = await listMyReviews();
    setReviews(nextReviews);
    setSelectedReviewId((current) => {
      if (nextReviews.length === 0) {
        return null;
      }
      if (current && nextReviews.some((review) => review.review_id === current)) {
        return current;
      }
      return nextReviews[0].review_id;
    });
  };

  useEffect(() => {
    void refresh().catch(() => setReviews([]));
  }, []);

  const activeReviewId = selectedReviewId ?? reviews[0]?.review_id ?? null;
  const selectedReview =
    reviews.find((review) => review.review_id === activeReviewId) ?? null;

  useEffect(() => {
    if (!selectedReview) {
      setReport(null);
      setDraft({});
      return;
    }

    let cancelled = false;
    setIsLoadingReport(true);
    setError(null);

    void getInternalReport(selectedReview.paper_id)
      .then((nextReport) => {
        if (cancelled) {
          return;
        }
        setReport(nextReport);
        setDraft(createExpertReviewDraft(nextReport.dimensions));
      })
      .catch((err) => {
        if (cancelled) {
          return;
        }
        setReport(null);
        setDraft({});
        setError(normalizeError(err));
      })
      .finally(() => {
        if (!cancelled) {
          setIsLoadingReport(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [selectedReview]);

  function updateDimensionDraft(
    dimensionKey: string,
    field: "expertScore" | "reason",
    value: string
  ): void {
    setDraft((current) => ({
      ...current,
      [dimensionKey]: {
        expertScore: current[dimensionKey]?.expertScore ?? "",
        reason: current[dimensionKey]?.reason ?? "",
        [field]: value,
      },
    }));
  }

  async function handleSubmit(): Promise<void> {
    if (!selectedReview || !report) {
      return;
    }

    const comments: ReviewSubmissionComment[] = [];
    for (const dimension of report.dimensions) {
      const currentDraft = draft[dimension.key];
      const reason = currentDraft?.reason?.trim() ?? "";
      const expertScoreRaw = currentDraft?.expertScore?.trim() ?? "";
      const expertScore = Number(expertScoreRaw);
      if (!expertScoreRaw || Number.isNaN(expertScore) || !reason) {
        setError("请补全所有维度的专家评分与修改理由");
        return;
      }
      comments.push({
        dimension_key: dimension.key,
        ai_score: dimension.ai.mean_score,
        expert_score: expertScore,
        reason,
      });
    }

    try {
      setError(null);
      setMessage(null);
      setIsSubmitting(true);
      await submitReview(selectedReview.review_id, comments);
      setMessage(`已提交《${selectedReview.paper_title ?? selectedReview.paper_id}》的专家复核。`);
      await refresh();
    } catch (err) {
      setError(normalizeError(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="expert-layout">
      <section className="panel expert-sidebar">
        <h2>专家工作台</h2>
        <p className="muted">选择任务后，可查看内部报告并逐维度提交专家复核意见。</p>
        {reviews.length === 0 ? (
          <p className="empty-state">暂无待处理复核任务。</p>
        ) : (
          <div className="paper-list">
            {reviews.map((review) => {
              const reviewLabel = review.paper_title ?? review.paper_id;
              return (
                <button
                  type="button"
                  key={review.review_id}
                  aria-label={`打开 ${reviewLabel}`}
                  className={`paper-row ${review.review_id === activeReviewId ? "selected" : ""}`}
                  onClick={() => setSelectedReviewId(review.review_id)}
                >
                  <strong>{reviewLabel}</strong>
                  <span>{formatStatusLabel(review.status)}</span>
                </button>
              );
            })}
          </div>
        )}
      </section>

      <section className="panel expert-main">
        <div className="section-heading">
          <div>
            <p className="eyebrow">复核详情</p>
            <h3>{selectedReview?.paper_title ?? selectedReview?.paper_id ?? "选择一条复核任务"}</h3>
          </div>
          {selectedReview ? <span className="count-chip">{formatStatusLabel(selectedReview.status)}</span> : null}
        </div>
        {message ? <p className="notice success">{message}</p> : null}
        {error ? <p className="notice error">{error}</p> : null}
        {!selectedReview ? (
          <p className="empty-state">请先选择一条专家复核任务。</p>
        ) : isLoadingReport ? (
          <p className="empty-state">正在加载内部报告...</p>
        ) : report ? (
          <>
            <div className="report-summary">
              <div>
                <span>任务编号</span>
                <strong>{selectedReview.task_id}</strong>
              </div>
              <div>
                <span>综合得分</span>
                <strong>
                  {formatWeightedTotalDisplay(report.weighted_total, report.precheck_status)}
                </strong>
              </div>
              <div>
                <span>评测轮数</span>
                <strong>{formatRoundsLabel(report.evaluation_config?.evaluation_rounds ?? 1)}</strong>
              </div>
            </div>
            {report.precheck_status === "reject" ? (
              <PrecheckRejectedSummary report={report} />
            ) : report.dimensions.length === 0 ? (
              <p className="empty-state">该内部报告暂无可复核维度。</p>
            ) : (
              <>
                {isPrecheckFlagged(report.precheck_status) ? (
                  <PrecheckFlaggedSummary report={report} />
                ) : null}
                <ReportAiOverview report={report} />
                <ReportRadarChart report={report} />
                <div className="expert-dimension-grid">
                  {report.dimensions.map((dimension) => (
                    <article className="expert-dimension-card" key={dimension.key}>
                      <ResultDimensionCard dimension={dimension} />
                      <div className="stack expert-form-fields">
                        <label className="stack">
                          <span>专家评分</span>
                          <input
                            aria-label={`${dimension.name_zh} 专家评分`}
                            type="number"
                            step="0.01"
                            min="0"
                            max="100"
                            value={draft[dimension.key]?.expertScore ?? ""}
                            onChange={(event) =>
                              updateDimensionDraft(
                                dimension.key,
                                "expertScore",
                                event.target.value
                              )
                            }
                          />
                        </label>
                        <label className="stack">
                          <span>修改理由</span>
                          <textarea
                            aria-label={`${dimension.name_zh} 修改理由`}
                            rows={4}
                            value={draft[dimension.key]?.reason ?? ""}
                            onChange={(event) =>
                              updateDimensionDraft(dimension.key, "reason", event.target.value)
                            }
                          />
                        </label>
                      </div>
                    </article>
                  ))}
                </div>
                <ExpertReviewCommentsSection report={report} />
                <button
                  type="button"
                  className="primary-action-button"
                  disabled={isSubmitting}
                  onClick={() => void handleSubmit()}
                >
                  {isSubmitting ? "提交中..." : "提交复核"}
                </button>
              </>
            )}
          </>
        ) : (
          <p className="empty-state">内部报告加载失败，请稍后重试。</p>
        )}
      </section>
    </div>
  );
}

function AdminDashboard() {
  const [users, setUsers] = useState<User[]>([]);
  const [invitations, setInvitations] = useState<InvitationListItem[]>([]);
  const [recoveryTasks, setRecoveryTasks] = useState<RecoveryTask[]>([]);
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([]);
  const [inviteEmail, setInviteEmail] = useState("new-user@example.com");
  const [inviteRole, setInviteRole] = useState("submitter");
  const [auditActionFilter, setAuditActionFilter] = useState("");
  const [latestInvitationLink, setLatestInvitationLink] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = async (options?: { auditAction?: string }): Promise<{ hasFailure: boolean }> => {
    const auditAction = options?.auditAction ?? auditActionFilter;
    const [userResult, invitationResult, taskResult, auditResult] = await Promise.allSettled([
      listUsers(),
      listInvitations(),
      getRecoveryTasks(),
      listAuditLogs(auditAction ? { action: auditAction } : undefined),
    ]);
    let hasFailure = false;

    if (userResult.status === "fulfilled") {
      setUsers(userResult.value);
    } else {
      hasFailure = true;
    }
    if (invitationResult.status === "fulfilled") {
      setInvitations(invitationResult.value.filter((invitation) => !invitation.is_used));
    } else {
      hasFailure = true;
    }
    if (taskResult.status === "fulfilled") {
      setRecoveryTasks(taskResult.value);
    } else {
      hasFailure = true;
    }
    if (auditResult.status === "fulfilled") {
      setAuditLogs(auditResult.value);
    } else {
      hasFailure = true;
    }

    if (hasFailure) {
      setError("部分数据加载失败，请稍后重试。");
      setNotice(null);
    } else if (error === "部分数据加载失败，请稍后重试。") {
      setError(null);
    }
    return { hasFailure };
  };

  useEffect(() => {
    void refresh();
  }, []);

  return (
    <div className="dashboard-grid">
      <section className="panel">
        <h2>管理工作台</h2>
        <form
          className="stack"
          onSubmit={async (event) => {
            event.preventDefault();
            try {
              const createdInvitation = await createInvitation(inviteEmail, inviteRole);
              const refreshResult = await refresh();
              setLatestInvitationLink(buildInvitationActivationUrl(createdInvitation.token));
              setNotice(`已创建邀请：${inviteEmail}`);
              if (!refreshResult.hasFailure) {
                setError(null);
              }
            } catch (err) {
              setError(normalizeError(err));
              setNotice(null);
            }
          }}
        >
          <label>
            邀请邮箱
            <input value={inviteEmail} onChange={(event) => setInviteEmail(event.target.value)} />
          </label>
          <label>
            角色
            <select value={inviteRole} onChange={(event) => setInviteRole(event.target.value)}>
              <option value="submitter">投稿者</option>
              <option value="editor">编辑</option>
              <option value="expert">专家</option>
              <option value="admin">管理员</option>
            </select>
          </label>
          <button type="submit">创建邀请</button>
        </form>
        {notice ? <p className="notice success">{notice}</p> : null}
        {error ? <p className="notice error">{error}</p> : null}
        {latestInvitationLink ? (
          <div className="stack">
            <p className="notice info">请将此链接发送给受邀用户。</p>
            <label>
              激活链接
              <input value={latestInvitationLink} readOnly />
            </label>
          </div>
        ) : null}
      </section>

      <section className="panel">
        <h3>邀请管理</h3>
        {invitations.length === 0 ? (
          <p className="empty-state">暂无待处理邀请。</p>
        ) : (
          <ul className="list admin-list">
            {invitations.map((invitation) => (
              <li key={invitation.id} className="admin-list-item">
                <div>
                  <strong>{invitation.email}</strong>
                  <p className="muted">
                    {formatRoleLabel(invitation.role)} · 过期时间 {formatDateTime(invitation.expires_at)}
                  </p>
                </div>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() =>
                    void (async () => {
                        try {
                          await revokeInvitation(invitation.id);
                          const refreshResult = await refresh();
                          setNotice(`已撤销邀请：${invitation.email}`);
                          if (!refreshResult.hasFailure) {
                            setError(null);
                          }
                        } catch (err) {
                          setError(normalizeError(err));
                          setNotice(null);
                      }
                    })()
                  }
                >
                  撤销邀请 {invitation.email}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h3>任务恢复</h3>
        {recoveryTasks.length === 0 ? (
          <p className="empty-state">暂无恢复任务。</p>
        ) : (
          <ul className="list admin-list">
            {recoveryTasks.map((task) => (
              <li key={task.task_id} className="admin-list-item">
                <div>
                  <strong>{task.paper_title?.trim() || task.paper_filename}</strong>
                  <p className="muted">
                    {task.task_id} · {formatStatusLabel(task.task_status)}
                  </p>
                  {task.failure_detail ? <p className="muted">{task.failure_detail}</p> : null}
                </div>
                <div className="action-row">
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() =>
                      void (async () => {
                        try {
                          await retryAdminTask(task.task_id);
                          const refreshResult = await refresh();
                          setNotice(`已重试任务：${task.task_id}`);
                          if (!refreshResult.hasFailure) {
                            setError(null);
                          }
                        } catch (err) {
                          setError(normalizeError(err));
                          setNotice(null);
                        }
                      })()
                    }
                  >
                    重试 {task.task_id}
                  </button>
                  <button
                    type="button"
                    className="secondary-button"
                    onClick={() =>
                      void (async () => {
                        try {
                          await closeAdminTask(task.task_id);
                          const refreshResult = await refresh();
                          setNotice(`已关闭任务：${task.task_id}`);
                          if (!refreshResult.hasFailure) {
                            setError(null);
                          }
                        } catch (err) {
                          setError(normalizeError(err));
                          setNotice(null);
                        }
                      })()
                    }
                  >
                    关闭 {task.task_id}
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h3>审计日志</h3>
        <div className="action-row">
          <label>
            操作筛选
            <select
              value={auditActionFilter}
              onChange={(event) => setAuditActionFilter(event.target.value)}
            >
              <option value="">全部</option>
              <option value="internal_report_access">internal_report_access</option>
              <option value="retry_task">retry_task</option>
              <option value="close_task">close_task</option>
            </select>
          </label>
          <button
            type="button"
            className="secondary-button"
            onClick={() => void refresh({ auditAction: auditActionFilter })}
          >
            筛选日志
          </button>
        </div>
        {auditLogs.length === 0 ? (
          <p className="empty-state">暂无审计日志。</p>
        ) : (
          <ul className="list admin-list">
            {auditLogs.map((log) => (
              <li key={log.id} className="admin-list-item">
                <div>
                  <strong>{log.action}</strong>
                  <p className="muted">
                    {log.object_type}:{log.object_id} · {log.result}
                  </p>
                  <p className="muted">
                    {log.actor_email ?? "system"} · {formatDateTime(log.created_at)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="panel">
        <h3>用户列表</h3>
        <ul className="list admin-list">
          {users.map((user) => (
            <li key={user.id} className="admin-list-item">
              <span>
                {user.display_name ?? user.email} - {formatRoleLabel(user.role)}
                {user.is_active ? "（启用）" : "（停用）"}
              </span>
            </li>
          ))}
        </ul>
        {users.length === 0 ? <p className="empty-state">暂无用户数据。</p> : null}
      </section>
    </div>
  );
}

function RoleDashboard({ user }: { user: User }) {
  if (user.role === "submitter") {
    return <SubmitterDashboard />;
  }
  if (user.role === "editor") {
    return <EditorDashboard />;
  }
  if (user.role === "expert") {
    return <ExpertDashboard />;
  }
  return <AdminDashboard />;
}

export function App({ initialUser }: AppProps) {
  const [user, setUser] = useState<User | null | undefined>(initialUser);
  const [activationToken, setActivationToken] = useState<string | null>(() =>
    readInvitationTokenFromLocation()
  );
  const [activationNotice, setActivationNotice] = useState<string | null>(null);
  const [loginEmail, setLoginEmail] = useState<string>("submitter@example.com");

  useEffect(() => {
    if (initialUser !== undefined) {
      return;
    }
    void getCurrentUser()
      .then((currentUser) => setUser(currentUser))
      .catch(() => setUser(null));
  }, [initialUser]);

  if (user === undefined) {
    return (
      <div className="shell">
        <p>正在加载会话...</p>
      </div>
    );
  }

  if (user === null) {
    return (
      <div className="shell auth-shell">
        {activationToken ? (
          <InvitationAcceptanceForm
            token={activationToken}
            onAccepted={(activatedUser) => {
              setLoginEmail(activatedUser.email);
              setActivationNotice(`账号已激活，请使用 ${activatedUser.email} 登录。`);
              setActivationToken(null);
              clearInvitationTokenFromLocation();
            }}
            onBackToLogin={() => {
              setActivationToken(null);
              clearInvitationTokenFromLocation();
            }}
          />
        ) : (
          <LoginForm
            onLoggedIn={setUser}
            initialEmail={loginEmail}
            notice={activationNotice}
          />
        )}
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="app-header">
        <div>
          <p className="eyebrow">试点演示</p>
          <h1>文科论文评价系统</h1>
          <p>{formatUserIdentity(user)}</p>
        </div>
        <button
          type="button"
          onClick={async () => {
            await logout();
            setUser(null);
          }}
        >
          退出登录
        </button>
      </header>
      <RoleDashboard user={user} />
    </div>
  );
}
