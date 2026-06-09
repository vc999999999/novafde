export type TargetPlatform = 'claude-code' | 'codex' | 'hermes-openclaw';

export type SkillType = 'automation' | 'workflow' | 'template' | 'constraint';

export type OutputLanguage = 'zh-CN' | 'en';

export type FreedomLevel = 'high' | 'medium' | 'low';

export type ValidationStrictness = 'loose' | 'normal' | 'strict';

export type GenerationStage =
  | 'normalizing'
  | 'injecting-rules'
  | 'splitting-workflow'
  | 'generating-ir'
  | 'rendering-files'
  | 'quality-gate'
  | 'packaging';

export type GenerationStatus = 'idle' | 'generating' | 'validating' | 'success' | 'failed';

export type ValidationLevel = 'pass' | 'warning' | 'blocking';

export interface TriggerInfo {
  intent: string;
  taskType: string;
  positiveExamples: string[];
  negativeExamples: string[];
  commonPhrases: string[];
  relatedFileTypes: string[];
  relatedTools: string[];
  relatedObjects: string[];
}

export interface WorkflowStep {
  id: string;
  purpose: string;
  action: string;
  input: string;
  output: string;
  validation: string;
  failureHandling: string;
}

export interface WorkflowInfo {
  objective: string;
  steps: WorkflowStep[];
  preconditions: string;
}

export interface ContextInfo {
  filesToRead: string[];
  needsReferences: boolean;
  needsScripts: boolean;
  needsAssets: boolean;
  loadingRule: string;
}

export interface KnowledgePitfall {
  id: string;
  description: string;
  goodExample: string;
  badExample: string;
}

export interface KnowledgeInfo {
  industryRules: string[];
  internalProcesses: string[];
  personalExperience: string[];
  pitfalls: KnowledgePitfall[];
}

export interface OutputControl {
  freedom: FreedomLevel;
  allowHardLimits: boolean;
  validationStrictness: ValidationStrictness;
  generateInstallGuide: boolean;
  allowDownloadWithWarnings: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'agent';
  content: string;
  timestamp: number;
}

export interface SkillDraft {
  id: string;
  status?: 'draft';
  name: string;
  displayName: string;
  language: OutputLanguage;
  skillType: SkillType;
  targetPlatforms: TargetPlatform[];
  trigger: TriggerInfo;
  workflow: WorkflowInfo;
  context: ContextInfo;
  knowledge: KnowledgeInfo;
  outputControl: OutputControl;
  supplement: {
    messages: ChatMessage[];
  };
  createdAt: number;
  updatedAt: number;
}

export interface GenerationResult {
  id: string;
  draftId: string;
  status: GenerationStatus;
  currentStage: GenerationStage | null;
  progress: number;
  files: FileNode[];
  skillMd: string;
  validation: ValidationItem[];
  blockingIssues: number;
  warnings: number;
  downloadInfo: DownloadInfo | null;
  startedAt: number;
  completedAt: number | null;
  errorMessage: string | null;
}

export interface FileNode {
  name: string;
  type: 'file' | 'folder';
  children?: FileNode[];
  size?: string;
}

export interface ValidationItem {
  id: string;
  ruleId: string;
  level: ValidationLevel;
  title: string;
  description: string;
  importance: string;
  suggestion: string;
  blocksDownload: boolean;
  field?: string;
}

export interface DownloadInfo {
  packageName: string;
  version: string;
  generatedAt: string;
  platforms: string[];
  fileCount: number;
  size: string;
}

export type HistoryItemStatus = 'draft' | 'generating' | 'validating' | 'downloadable' | 'failed';

export interface HistoryItem {
  id: string;
  displayName: string;
  name: string;
  status: HistoryItemStatus;
  platforms: string[];
  createdAt: string;
  updatedAt: string;
}

// --- Provider config types (PRD FR-10, FR-11) ---

export type ProviderProtocol = 'claude' | 'openai-compatible';

export type ProviderRole = 'generation' | 'repair' | 'validation-explanation';

export type ProviderTestStatus = 'passed' | 'failed';

export type ProviderFailureCategory =
  | 'auth-missing'
  | 'auth-failed'
  | 'url-error'
  | 'model-not-found'
  | 'protocol-mismatch'
  | 'timeout'
  | 'network-error'
  | 'unknown';

export interface ApiKeyRef {
  type: 'env';
  name: string;
}

export interface ProviderTestResult {
  status: ProviderTestStatus;
  protocol: ProviderProtocol;
  model: string;
  latencyMs: number;
  testedAt: string;
  failureCategory: ProviderFailureCategory | null;
  message: string;
}

export interface ModelProviderConfig {
  id: string;
  name: string;
  protocol: ProviderProtocol;
  baseUrl: string;
  apiKeyRef: ApiKeyRef;
  defaultModel: string;
  roles: ProviderRole[];
  timeoutMs: number;
  retries: number;
  streaming: boolean;
  customHeaders: Record<string, string>;
  enabled: boolean;
  lastTest: ProviderTestResult | null;
}

export type ModelProviderPayload = Omit<ModelProviderConfig, 'id' | 'lastTest'> & {
  apiKey?: string;
};

export type ConnectionTestStatus = 'idle' | 'testing' | 'success' | 'error';

export interface ConnectionTestResult {
  status: ConnectionTestStatus;
  protocol?: ProviderProtocol;
  modelId?: string;
  latencyMs?: number;
  errorCategory?: 'missing_key' | 'auth_failed' | 'bad_url' | 'model_not_found' | 'protocol_mismatch' | 'timeout' | 'unknown';
  errorMessage?: string;
}

// --- CLI help types (PRD FR-12) ---

export type DangerLevel = 'low' | 'medium' | 'high';

export interface CliCommandHelp {
  name: string;
  command: string;
  purpose: string;
  repeatable: boolean;
  reads: string[];
  writes: string[];
  requiresNetwork: boolean;
  dangerLevel: DangerLevel;
  failureSummary: string;
}

export interface QualityRule {
  id: string;
  category: string;
  title: string;
  description: string;
  severity: 'blocking' | 'warning';
}

// --- Page type ---

export type Page = 'create' | 'history' | 'rules' | 'settings' | 'local';

// --- App mode ---

export type AppMode = 'local' | 'server';
