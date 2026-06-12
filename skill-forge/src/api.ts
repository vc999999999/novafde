import type {
  AppSettings,
  CliCommandHelp,
  DiagnosticMetrics,
  ErrorPattern,
  GenerationResult,
  HistoryItem,
  InstallRequest,
  InstallResult,
  ModelConnectionStatus,
  ModelProviderConfig,
  ModelProviderPayload,
  ProviderTestResult,
  QualityRule,
  QualityEvaluationReport,
  SkillDraft,
  SkillSpecResponse,
  SupplementAnswer,
} from './types';

export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, message: string, detail: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

function apiUrl(path: string) {
  return path;
}

async function readError(response: Response): Promise<{ message: string; detail: unknown }> {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') return { message: body.detail, detail: body };
      return { message: JSON.stringify(body.detail ?? body), detail: body };
    } catch {
      // JSON parse failed, fall through to text handling
    }
  }
  const text = await response.text().catch(() => '');
  return { message: text || response.statusText, detail: text };
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 30_000);
  try {
    const response = await fetch(apiUrl(path), {
      ...init,
      headers,
      signal: controller.signal,
    });

    if (!response.ok) {
      const error = await readError(response);
      throw new ApiError(response.status, error.message, error.detail);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json() as Promise<T>;
  } finally {
    clearTimeout(timeoutId);
  }
}

export function listHistory() {
  return apiRequest<HistoryItem[]>('/api/history');
}

export function deleteHistoryItem(draftId: string) {
  return apiRequest<void>(`/api/drafts/${encodeURIComponent(draftId)}`, {
    method: 'DELETE',
  });
}

export function listRules() {
  return apiRequest<QualityRule[]>('/api/rules');
}

export function getDiagnosticMetrics() {
  return apiRequest<DiagnosticMetrics>('/api/diagnostics/metrics');
}

export function listErrorPatterns() {
  return apiRequest<ErrorPattern[]>('/api/diagnostics/error-patterns');
}

export function listCliCommands() {
  return apiRequest<CliCommandHelp[]>('/api/cli/commands');
}

export function patchDraft(draftId: string, draft: SkillDraft) {
  return apiRequest<SkillDraft>(`/api/drafts/${encodeURIComponent(draftId)}`, {
    method: 'PATCH',
    body: JSON.stringify(draft),
  });
}

export function createDraft(draft: SkillDraft) {
  return apiRequest<SkillDraft>('/api/drafts', {
    method: 'POST',
    body: JSON.stringify(draft),
  });
}

export function generateDraft(draftId: string) {
  return apiRequest<GenerationResult>(`/api/drafts/${encodeURIComponent(draftId)}/generate`, {
    method: 'POST',
  });
}

export function startGeneration(draftId: string) {
  return apiRequest<GenerationResult>('/api/generations', {
    method: 'POST',
    body: JSON.stringify({
      draftId,
      qualityMode: 'strict',
      maxRepairRounds: 3,
    }),
  });
}

export function getGeneration(generationId: string) {
  return apiRequest<GenerationResult>(
    `/api/generations/${encodeURIComponent(generationId)}`,
  );
}

export function cancelGeneration(generationId: string) {
  return apiRequest<GenerationResult>(
    `/api/generations/${encodeURIComponent(generationId)}/cancel`,
    { method: 'POST' },
  );
}

export function getGenerationQuality(generationId: string) {
  return apiRequest<QualityEvaluationReport>(
    `/api/generations/${encodeURIComponent(generationId)}/quality`,
  );
}

export function getGenerationSpec(generationId: string) {
  return apiRequest<SkillSpecResponse>(
    `/api/generations/${encodeURIComponent(generationId)}/spec`,
  );
}

export function submitGenerationSupplement(
  generationId: string,
  answers: SupplementAnswer[],
  skip = false,
) {
  return apiRequest<GenerationResult>(
    `/api/generations/${encodeURIComponent(generationId)}/supplement`,
    {
      method: 'POST',
      body: JSON.stringify({ answers, skip }),
    },
  );
}

export function regenerateGeneration(generationId: string) {
  return apiRequest<GenerationResult>(`/api/generations/${encodeURIComponent(generationId)}/regenerate`, {
    method: 'POST',
  });
}

export function installGeneration(generationId: string, payload: InstallRequest = {}) {
  return apiRequest<InstallResult>(
    `/api/generations/${encodeURIComponent(generationId)}/install`,
    {
      method: 'POST',
      body: JSON.stringify(payload),
    },
  );
}

export function toGenerationDownloadUrl(generationId: string) {
  return apiUrl(`/api/generations/${encodeURIComponent(generationId)}/download`);
}

export function listModelProviders() {
  return apiRequest<ModelProviderConfig[]>('/api/model-providers');
}

export function createModelProvider(provider: ModelProviderPayload) {
  return apiRequest<ModelProviderConfig>('/api/model-providers', {
    method: 'POST',
    body: JSON.stringify(provider),
  });
}

export function updateModelProvider(providerId: string, updates: Partial<ModelProviderPayload>) {
  return apiRequest<ModelProviderConfig>(`/api/model-providers/${encodeURIComponent(providerId)}`, {
    method: 'PATCH',
    body: JSON.stringify(updates),
  });
}

export function deleteModelProvider(providerId: string) {
  return apiRequest<void>(`/api/model-providers/${encodeURIComponent(providerId)}`, {
    method: 'DELETE',
  });
}

export function testModelProvider(providerId: string) {
  return apiRequest<ProviderTestResult>(`/api/model-providers/${encodeURIComponent(providerId)}/test`, {
    method: 'POST',
  });
}

export function getModelConnectionStatus() {
  return apiRequest<ModelConnectionStatus>('/api/providers/connection-status');
}

export function getSettings() {
  return apiRequest<AppSettings>('/api/settings');
}

export function saveSettings(settings: AppSettings) {
  return apiRequest<AppSettings>('/api/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  });
}
