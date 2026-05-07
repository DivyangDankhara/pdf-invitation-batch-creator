import type {
  FontInfo,
  GeneratedFile,
  GuestImportResult,
  JobInfo,
  TemplateConfig,
  TemplateInfo,
} from "./types";

export const API_BASE = "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text();
    try {
      const parsed = JSON.parse(text) as { detail?: string };
      throw new Error(parsed.detail ?? response.statusText);
    } catch {
      throw new Error(text || response.statusText);
    }
  }
  return (await response.json()) as T;
}

export async function createSession(): Promise<string> {
  const response = await fetch(`${API_BASE}/api/sessions`, { method: "POST" });
  const data = await parseResponse<{ sessionId: string }>(response);
  return data.sessionId;
}

export async function getFonts(sessionId?: string): Promise<FontInfo[]> {
  const path = sessionId ? `/api/sessions/${sessionId}/fonts` : "/api/fonts";
  return parseResponse<FontInfo[]>(await fetch(`${API_BASE}${path}`));
}

async function upload<T>(url: string, file: File): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  return parseResponse<T>(
    await fetch(url, {
      method: "POST",
      body: form,
    }),
  );
}

export function uploadTemplate(sessionId: string, file: File): Promise<TemplateInfo> {
  return upload(`${API_BASE}/api/sessions/${sessionId}/template`, file);
}

export function uploadGuests(sessionId: string, file: File): Promise<GuestImportResult> {
  return upload(`${API_BASE}/api/sessions/${sessionId}/guests`, file);
}

export function uploadFont(sessionId: string, file: File): Promise<FontInfo> {
  return upload(`${API_BASE}/api/sessions/${sessionId}/fonts`, file);
}

export function pageImageUrl(sessionId: string, pageIndex: number): string {
  return `${API_BASE}/api/sessions/${sessionId}/template/pages/${pageIndex}/image`;
}

export async function previewPage(
  sessionId: string,
  config: TemplateConfig,
  rowIndex: number,
  pageIndex: number,
): Promise<Blob> {
  const response = await fetch(`${API_BASE}/api/sessions/${sessionId}/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config, rowIndex, pageIndex }),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail ?? response.statusText);
  }
  return response.blob();
}

export async function generatePdfs(sessionId: string, config: TemplateConfig): Promise<JobInfo> {
  return parseResponse<JobInfo>(
    await fetch(`${API_BASE}/api/sessions/${sessionId}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ config }),
    }),
  );
}

export async function getJob(jobId: string): Promise<JobInfo> {
  return parseResponse<JobInfo>(await fetch(`${API_BASE}/api/jobs/${jobId}`));
}

export async function getJobFiles(jobId: string): Promise<GeneratedFile[]> {
  return parseResponse<GeneratedFile[]>(await fetch(`${API_BASE}/api/jobs/${jobId}/files`));
}

export function fileUrl(jobId: string, fileId: string): string {
  return `${API_BASE}/api/jobs/${jobId}/files/${fileId}`;
}
