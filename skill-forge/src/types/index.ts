export type TargetPlatform = 'claude-code' | 'codex' | 'hermes-openclaw';

export type GenerationStage =
  | 'queued'
  | 'normalizing'
  | 'generating-workflow'
  | 'generating-knowledge'
  | 'generating-quality'
  | 'generating-trace'
  | 'injecting-rules'
  | 'splitting-workflow'
  | 'generating-ir'
  | 'validating-schema'
  | 'rendering-files'
  | 'running-validation-checks'
  | 'evaluating-activation'
  | 'evaluating-implementation'
  | 'aggregating-scores'
  | 'repairing'
  | 'awaiting-user-input'
  | 'selecting-best-candidate'
  | 'quality-gate'
  | 'packaging';

export type GenerationStageKey = 'workflow' | 'knowledge' | 'quality' | 'trace';

export interface GenerationStageAttempt {
  stage: GenerationStageKey;
  attempt: number;
  status: 'succeeded' | 'failed';
  errors: string[];
  result: Record<string, unknown>;
  providerId: string | null;
  modelName: string | null;
  promptVersion: string;
  inputTokens: number;
  outputTokens: number;
  durationMs: number;
  startedAt: number;
  completedAt: number;
}

export type GenerationStatus =
  | 'queued'
  | 'normalizing'
  | 'generating_initial_ir'
  | 'validating_schema'
  | 'rendering_candidate'
  | 'running_validation_checks'
  | 'evaluating_activation'
  | 'evaluating_implementation'
  | 'aggregating_scores'
  | 'repairing_round_1'
  | 'repairing_round_2'
  | 'repairing_round_3'
  | 'awaiting_user_input'
  | 'selecting_best_candidate'
  | 'packaging_high_quality'
  | 'packaging_low_score'
  | 'succeeded'
  | 'degraded'
  | 'interrupted'
  | 'failed';

export type ValidationLevel = 'pass' | 'warning' | 'blocking';

export interface PurposeInfo {
  usage: string;
  desiredOutcome: string;
  process: string[];
  completionCriteria: string;
  specialCases: string;
  specialCaseItems?: Array<{
    id: string;
    statement: string;
    source: SpecItemSource;
    required: boolean;
  }>;
}

export interface KnowledgePitfall {
  id: string;
  description: string;
  goodExample: string;
  badExample: string;
}

export interface KnowledgeInfo {
  professionalInformation: string[];
  mandatoryRules: string[];
  pitfalls: KnowledgePitfall[];
  relatedSkills: string[];
}

export interface SkillDraft {
  id: string;
  status?: 'draft';
  name: string;
  displayName: string;
  targetPlatforms: TargetPlatform[];
  purpose: PurposeInfo;
  knowledge: KnowledgeInfo;
  supplement: {
    content: string;
  };
  createdAt: number;
  updatedAt: number;
}

export type SpecItemSource = 'user' | 'system' | 'derived';

export interface SkillSpec {
  schemaVersion: string;
  revision: number;
  identity: {
    skillName: string;
    displayName: string;
    targetPlatforms: TargetPlatform[];
    outputLanguage: 'zh-CN' | 'en';
  };
  activationContract: {
    usage: string;
    desiredOutcome: string;
  };
  workflowStages: Array<{
    id: string;
    statement: string;
    source: SpecItemSource;
    required: boolean;
  }>;
  completionCriteria: string;
  specialCases: string;
  incrementalKnowledge: string[];
  pitfalls: KnowledgePitfall[];
  hardRestrictions: string[];
  restrictionItems: Array<{
    id: string;
    statement: string;
    source: SpecItemSource;
  }>;
  fileContract: {
    needsReferences: boolean;
    needsScripts: boolean;
    needsAssets: boolean;
  };
  relatedSkills: Array<{
    name: string;
    source: SpecItemSource;
  }>;
  acceptanceCriteria: Array<{
    id: string;
    statement: string;
    source: SpecItemSource;
    required: boolean;
  }>;
  userSupplements?: Array<{
    id: string;
    question: string;
    statement: string;
    source: SpecItemSource;
  }>;
  sourceIssueIds: string[];
}

export interface SkillSpecResponse {
  current: SkillSpec;
  revision: number;
  sha256: string;
  revisions: Array<{
    revision: number;
    sha256: string;
    createdAt: number;
    sourceIssueIds: string[];
  }>;
}

export interface GenerationResult {
  id: string;
  runId: string;
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
  modelProviderId?: string | null;
  modelProtocol?: ProviderProtocol | null;
  providerConnectionRisk?: string | null;
  currentRound: number;
  maxRepairRounds: number;
  bestAttemptId: string | null;
  finalAttemptId: string | null;
  finalRound: number | null;
  awaitingUserInputIssueIds: string[];
  promptedIssueIds: string[];
  userQuestions: UserQuestion[];
  qualityReport: QualityEvaluationReport | null;
  qualityPolicyVersion: string;
  promptBundleVersion: string;
  failureCode: string | null;
  supplementScoreDelta: number | null;
  skillSpecAvailable: boolean;
  skillSpecRevision: number | null;
  skillSpecSha256: string | null;
  stageAttempt: number;
  stageMaxAttempts: number;
  completedStages: GenerationStageKey[];
  stageMessage: string;
  cancelRequested: boolean;
  stageAttempts: GenerationStageAttempt[];
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
  inputLayer?: 'required' | 'derived' | 'advanced' | null;
}

export interface DownloadInfo {
  packageName: string;
  version: string;
  generatedAt: string;
  platforms: string[];
  fileCount: number;
  size: string;
}

export type HistoryItemStatus =
  | 'draft'
  | 'generating'
  | 'validating'
  | 'awaiting-user-input'
  | 'downloadable'
  | 'degraded'
  | 'interrupted'
  | 'failed';

export interface HistoryItem {
  id: string;
  generationId: string | null;
  displayName: string;
  name: string;
  status: HistoryItemStatus;
  platforms: string[];
  createdAt: string;
  updatedAt: string;
}

// --- Provider config types (PRD FR-10, FR-11) ---

export type ProviderProtocol = 'anthropic' | 'openai-compatible';

export type ProviderRole =
  | 'generation'
  | 'repair'
  | 'activation-evaluation'
  | 'implementation-evaluation'
  | 'validation-explanation';

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
  inputPricePerMillionTokens: number;
  outputPricePerMillionTokens: number;
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

export interface ErrorPattern {
  id: string;
  patternId: string;
  category: string;
  criterion: string;
  severity: QualitySeverity;
  triggerConditions: string[];
  suggestedFix: string;
  occurrenceCount: number;
  resolutionRate: number;
  status: string;
  version: string;
  updatedAt: number;
}

export interface DiagnosticMetrics {
  runCount: number;
  firstRoundStrictPassRate: number;
  finalStrictPassRate: number;
  degradedDeliveryRate: number;
  technicalFailureRate: number;
  averageRepairRounds: number;
  averageScoreImprovement: number;
  scoreRegressionRate: number;
  supplementPromptRate: number;
  supplementSkipRate: number;
  criterionAverageScores: Record<string, number>;
  issueFrequency: ErrorPattern[];
  models: Record<string, {
    calls: number;
    inputTokens: number;
    outputTokens: number;
    estimatedCostUsd: number;
    p95LatencyMs: number;
    strictPassRate: number;
  }>;
  alerts: string[];
}

// --- App settings ---

export interface AppSettings {
  defaultGenerateProvider: string;
  defaultRepairProvider: string;
  defaultValidateProvider: string;
  blockOnMissingConfig: boolean;
}

export type QualitySeverity =
  | 'security_blocker'
  | 'structure_blocker'
  | 'quality_error'
  | 'warning'
  | 'info';

export type InputControl = 'short-text' | 'long-text' | 'single-select' | 'multi-select';

export interface UserQuestion {
  issueId: string;
  question: string;
  inputControl: InputControl;
  options: string[];
  existingAnswer: string | string[] | null;
}

export interface QualityIssue {
  issueId: string;
  source: 'validation' | 'activation' | 'implementation';
  criterion: string;
  severity: QualitySeverity;
  score: number | null;
  reason: string;
  evidence: string[];
  suggestion: string;
  affectedPaths: string[];
  autoFixable: boolean;
  requiresUserInput: boolean;
  userQuestion: string | null;
  inputControl: InputControl | null;
  options: string[];
  specItemIds: string[];
}

export interface CriterionScore {
  criterion: string;
  score: number;
  reason: string;
  evidence: string[];
  suggestion: string;
  requiresUserInput: boolean;
  userQuestion: string | null;
  inputControl: InputControl | null;
  options: string[];
}

export interface JudgeEvaluation {
  dimension: 'activation' | 'implementation';
  criterionScores: CriterionScore[];
  dimensionScore: number;
  summary: string;
  issues: QualityIssue[];
  confidence: number;
  requiresRepair: boolean;
  requiresUserInput: boolean;
  userQuestions: UserQuestion[];
}

export interface QualityEvaluationReport {
  attemptId: string;
  validationScore: number;
  activationScore: number | null;
  implementationScore: number | null;
  overallScore: number | null;
  passedStrictGate: boolean;
  passedDegradedGate: boolean;
  blockingIssueCount: number;
  issues: QualityIssue[];
  activation: JudgeEvaluation | null;
  implementation: JudgeEvaluation | null;
  rubricVersion: string;
  evaluatedAt: number;
}

export type ModelConnectionState =
  | 'unconfigured'
  | 'connecting'
  | 'connected'
  | 'disconnected'
  | 'error';

export interface ModelConnectionProvider {
  id: string;
  name: string;
  model: string;
  protocol: ProviderProtocol;
}

export interface ModelConnectionStatus {
  status: ModelConnectionState;
  generationProvider: ModelConnectionProvider | null;
  judgeProvider: ModelConnectionProvider | null;
  checkedAt: string | null;
  message: string;
}

export interface SupplementAnswer {
  issueId: string;
  answer: string | string[];
}

// --- Page type ---

export type Page = 'create' | 'history' | 'rules' | 'settings' | 'local';
