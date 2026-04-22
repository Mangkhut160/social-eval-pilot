import type {
  AuditLogItem,
  InvitationCreateResult,
  InvitationListItem,
  PaperOptions,
  PaperListItem,
  PaperStatus,
  RecoveryTask,
  ReportHistoryItem,
  ReportSnapshot,
  ReviewQueueItem,
  ReviewSubmissionComment,
  ReviewTask,
  User,
  UserListResponse,
} from "./types";

type ReportType = "public" | "internal";
type ExportFormat = "json" | "pdf";
type UploadPaperOptions = {
  selectedModels: string[];
  evaluationRounds: number;
};

function resolveApiBase(): string {
  const configuredBase = import.meta.env.VITE_API_BASE?.trim();
  if (configuredBase) {
    return configuredBase.replace(/\/$/, "");
  }
  if (typeof window !== "undefined" && window.location.origin) {
    return window.location.origin;
  }
  return "";
}

const API_BASE = resolveApiBase();

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export async function getCurrentUser(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export async function login(email: string, password: string): Promise<User> {
  return apiFetch<User>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function acceptInvitation(payload: {
  token: string;
  displayName: string;
  password: string;
}): Promise<User> {
  return apiFetch<User>("/api/auth/invitations/accept", {
    method: "POST",
    body: JSON.stringify({
      token: payload.token,
      display_name: payload.displayName,
      password: payload.password,
    }),
  });
}

export async function logout(): Promise<void> {
  await apiFetch<void>("/api/auth/logout", { method: "POST" });
}

export async function listPapers(): Promise<PaperListItem[]> {
  const result = await apiFetch<{ items: PaperListItem[] }>("/api/papers");
  return result.items;
}

export async function getPaperOptions(): Promise<PaperOptions> {
  return apiFetch<PaperOptions>("/api/papers/options");
}

export async function uploadPaper(
  file: File,
  options: UploadPaperOptions
): Promise<{ paper_id: string; task_id: string }> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("provider_names", options.selectedModels.join(","));
  formData.append("evaluation_rounds", String(options.evaluationRounds));
  const response = await fetch(`${API_BASE}/api/papers`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }
  return response.json() as Promise<{ paper_id: string; task_id: string }>;
}

export async function getPaperStatus(paperId: string): Promise<PaperStatus> {
  return apiFetch<PaperStatus>(`/api/papers/${paperId}/status`);
}

export async function startPaperEvaluation(
  paperId: string
): Promise<{ paper_id: string; task_id: string }> {
  return apiFetch<{ paper_id: string; task_id: string }>(`/api/papers/${paperId}/start`, {
    method: "POST",
  });
}

export async function deletePaper(paperId: string): Promise<void> {
  await apiFetch<void>(`/api/papers/${paperId}`, {
    method: "DELETE",
  });
}

export async function listReportHistory(
  paperId: string,
  reportType: ReportType = "public"
): Promise<ReportHistoryItem[]> {
  const query = new URLSearchParams({ report_type: reportType });
  const result = await apiFetch<{ items: ReportHistoryItem[] }>(
    `/api/papers/${paperId}/report/history?${query.toString()}`
  );
  return result.items;
}

export async function getPublicReport(
  paperId: string,
  version?: number
): Promise<ReportSnapshot> {
  const query = new URLSearchParams();
  if (version !== undefined) {
    query.set("version", String(version));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<ReportSnapshot>(`/api/papers/${paperId}/report${suffix}`);
}

export async function getInternalReport(
  paperId: string,
  version?: number
): Promise<ReportSnapshot> {
  const query = new URLSearchParams();
  if (version !== undefined) {
    query.set("version", String(version));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  return apiFetch<ReportSnapshot>(`/api/papers/${paperId}/internal-report${suffix}`);
}

export function getReportExportUrl(
  paperId: string,
  format: ExportFormat,
  reportType: ReportType = "public",
  version?: number
): string {
  const query = new URLSearchParams({
    format,
    report_type: reportType,
  });
  if (version !== undefined) {
    query.set("version", String(version));
  }
  return `${API_BASE}/api/papers/${paperId}/report/export?${query.toString()}`;
}

export async function getReviewQueue(): Promise<ReviewQueueItem[]> {
  const result = await apiFetch<{ items: ReviewQueueItem[] }>("/api/reviews/queue");
  return result.items;
}

export async function listExperts(): Promise<User[]> {
  const result = await apiFetch<UserListResponse>("/api/users/experts");
  return result.items;
}

export async function assignExpert(taskId: string, expertIds: string[]): Promise<void> {
  await apiFetch(`/api/reviews/${taskId}/assign`, {
    method: "POST",
    body: JSON.stringify({ expert_ids: expertIds }),
  });
}

export async function listMyReviews(): Promise<ReviewTask[]> {
  const result = await apiFetch<{ items: ReviewTask[] }>("/api/reviews/mine");
  return result.items;
}

export async function submitReview(
  reviewId: string,
  comments: ReviewSubmissionComment[]
): Promise<void> {
  await apiFetch(`/api/reviews/${reviewId}/submit`, {
    method: "POST",
    body: JSON.stringify({
      comments,
    }),
  });
}

export async function listUsers(): Promise<User[]> {
  const result = await apiFetch<UserListResponse>("/api/users");
  return result.items;
}

export async function createInvitation(
  email: string,
  role: string
): Promise<InvitationCreateResult> {
  return apiFetch<InvitationCreateResult>("/api/users/invitations", {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
}

export async function listInvitations(): Promise<InvitationListItem[]> {
  const result = await apiFetch<{ items: InvitationListItem[] }>("/api/users/invitations");
  return result.items;
}

export async function revokeInvitation(invitationId: string): Promise<void> {
  await apiFetch<void>(`/api/users/invitations/${invitationId}`, {
    method: "DELETE",
  });
}

export async function getRecoveryTasks(): Promise<RecoveryTask[]> {
  const result = await apiFetch<{ items: RecoveryTask[] }>("/api/admin/tasks");
  return result.items;
}

export async function retryAdminTask(taskId: string): Promise<void> {
  await apiFetch(`/api/admin/tasks/${taskId}/retry`, {
    method: "POST",
  });
}

export async function closeAdminTask(taskId: string): Promise<void> {
  await apiFetch(`/api/admin/tasks/${taskId}/close`, {
    method: "POST",
  });
}

export async function listAuditLogs(filters?: {
  action?: string;
  objectType?: string;
  limit?: number;
}): Promise<AuditLogItem[]> {
  const query = new URLSearchParams();
  if (filters?.action) {
    query.set("action", filters.action);
  }
  if (filters?.objectType) {
    query.set("object_type", filters.objectType);
  }
  if (filters?.limit) {
    query.set("limit", String(filters.limit));
  }
  const suffix = query.toString() ? `?${query.toString()}` : "";
  const result = await apiFetch<{ items: AuditLogItem[] }>(`/api/admin/audit-logs${suffix}`);
  return result.items;
}
