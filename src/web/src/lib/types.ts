export type User = {
  id: string;
  email: string;
  role: "submitter" | "editor" | "expert" | "admin";
  display_name?: string | null;
  is_active: boolean;
};

export type EvaluationConfig = {
  selected_models: string[];
  evaluation_rounds: number;
};

export type ModelOption = {
  name: string;
  label: string;
  source: string;
};

export type PaperOptions = {
  model_options: ModelOption[];
  default_selected_models: string[];
  max_selected_models: number;
  default_rounds: number;
  min_rounds: number;
  max_rounds: number;
};

export type PaperListItem = {
  paper_id: string;
  title?: string | null;
  original_filename: string;
  paper_status: string;
  precheck_status?: string | null;
};

export type ReliabilitySummary = {
  total_dimensions: number;
  high_confidence_count: number;
  low_confidence_count: number;
  overall_high_confidence: boolean;
};

export type PaperStatus = {
  paper_id: string;
  task_id: string;
  paper_status: string;
  task_status: string;
  precheck_status?: string | null;
  failure_stage?: string | null;
  failure_detail?: string | null;
  reliability_summary?: ReliabilitySummary | null;
  evaluation_config: EvaluationConfig;
};

export type ReportHistoryItem = {
  report_id: string;
  report_type: "public" | "internal";
  version: number;
  is_current: boolean;
  weighted_total: number;
  precheck_status?: string | null;
  created_at: string;
  available_export_formats: ("json" | "pdf")[];
};

export type PrecheckResult = {
  status?: string | null;
  issues?: string[];
  recommendation?: string | null;
};

export type ReportDimension = {
  key: string;
  name_zh: string;
  name_en: string;
  weight: number;
  ai: {
    mean_score: number;
    std_score: number;
    is_high_confidence: boolean;
    model_scores?: Record<string, number>;
    evidence_quotes?: string[];
    analysis?: string[];
  };
};

export type ExpertReviewSummary = {
  review_id: string;
  status: string;
  expert_id?: string;
  version?: number;
  completed_at?: string | null;
  comments: Array<{
    dimension_key: string;
    expert_score: number;
    reason: string;
  }>;
};

export type ReportSnapshot = {
  report_type: "public" | "internal";
  paper_id: string;
  task_id: string;
  paper_title?: string;
  precheck_status?: string | null;
  precheck_result?: PrecheckResult | null;
  evaluation_config: EvaluationConfig;
  weighted_total: number;
  dimensions: ReportDimension[];
  expert_reviews: ExpertReviewSummary[];
  radar_chart?: {
    labels: string[];
    values: number[];
    image_base64?: string;
  };
};

export type ReviewQueueItem = {
  task_id: string;
  paper_id: string;
  paper_title?: string | null;
  paper_status?: string | null;
  task_status: string;
  low_confidence_dimensions: string[];
  needs_assignment: boolean;
  assigned_reviews: Array<{
    review_id: string;
    expert_id: string;
    expert_email: string;
    expert_display_name?: string | null;
    status: string;
    completed_at?: string | null;
  }>;
};

export type ReviewTask = {
  review_id: string;
  task_id: string;
  paper_id: string;
  paper_title?: string | null;
  status: string;
};

export type ReviewSubmissionComment = {
  dimension_key: string;
  ai_score: number;
  expert_score: number;
  reason: string;
};

export type UserListResponse = {
  items: User[];
};

export type InvitationListItem = {
  id: string;
  email: string;
  role: "submitter" | "editor" | "expert" | "admin";
  token: string;
  invited_by: string;
  is_used: boolean;
  expires_at: string;
  created_at: string;
};

export type InvitationCreateResult = {
  id: string;
  email: string;
  role: "submitter" | "editor" | "expert" | "admin";
  token: string;
  expires_at: string;
};

export type RecoveryTask = {
  task_id: string;
  paper_id: string;
  paper_title?: string | null;
  paper_filename: string;
  task_status: string;
  paper_status: string;
  failure_stage?: string | null;
  failure_detail?: string | null;
  created_at: string;
  updated_at: string;
};

export type AuditLogItem = {
  id: string;
  actor_id?: string | null;
  actor_email?: string | null;
  object_type: string;
  object_id: string;
  action: string;
  result: string;
  details?: Record<string, unknown> | null;
  created_at: string;
};
