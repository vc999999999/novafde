import type {
  CliCommandHelp,
  GenerationResult,
  HistoryItem,
  ModelProviderConfig,
  ModelProviderPayload,
  ProviderTestResult,
  QualityRule,
  SkillDraft,
} from './types';

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

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
  return `${API_BASE_URL}${path}`;
}

async function readError(response: Response) {
  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    const body = await response.json();
    if (typeof body?.detail === 'string') return { message: body.detail, detail: body };
    return { message: JSON.stringify(body.detail ?? body), detail: body };
  }
  const text = await response.text();
  return { message: text || response.statusText, detail: text };
}

async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(apiUrl(path), {
    ...init,
    headers,
  });

  if (!response.ok) {
    const error = await readError(response);
    throw new ApiError(response.status, error.message, error.detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function listHistory() {
  return apiRequest<HistoryItem[]>('/api/history');
}

export function listRules() {
  return apiRequest<QualityRule[]>('/api/rules');
}

export function listCliCommands() {
  return apiRequest<CliCommandHelp[]>('/api/cli/commands');
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

export function regenerateGeneration(generationId: string) {
  return apiRequest<GenerationResult>(`/api/generations/${encodeURIComponent(generationId)}/regenerate`, {
    method: 'POST',
  });
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
