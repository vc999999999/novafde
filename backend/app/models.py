from __future__ import annotations

from typing import Annotated, Any, Literal
from urllib.parse import urlparse

from pydantic import BaseModel, BeforeValidator, Field, field_validator, model_validator


TargetPlatform = Literal["claude-code", "codex", "hermes-openclaw"]
OutputLanguage = Literal["zh-CN", "en"]
FreedomLevel = Literal["high", "medium", "low"]
GenerationStage = Literal[
    "queued",
    "normalizing",
    "injecting-rules",
    "splitting-workflow",
    "generating-ir",
    "validating-schema",
    "rendering-files",
    "running-validation-checks",
    "evaluating-activation",
    "evaluating-implementation",
    "aggregating-scores",
    "repairing",
    "awaiting-user-input",
    "selecting-best-candidate",
    "quality-gate",
    "packaging",
]
GenerationStatus = Literal[
    "queued",
    "normalizing",
    "generating_initial_ir",
    "validating_schema",
    "rendering_candidate",
    "running_validation_checks",
    "evaluating_activation",
    "evaluating_implementation",
    "aggregating_scores",
    "repairing_round_1",
    "repairing_round_2",
    "repairing_round_3",
    "awaiting_user_input",
    "selecting_best_candidate",
    "packaging_high_quality",
    "packaging_low_score",
    "succeeded",
    "degraded",
    "interrupted",
    "failed",
]
ValidationLevel = Literal["pass", "warning", "blocking"]
HistoryItemStatus = Literal[
    "draft",
    "generating",
    "validating",
    "awaiting-user-input",
    "downloadable",
    "degraded",
    "interrupted",
    "failed",
]
InputLayer = Literal["required", "derived", "advanced"]
def _normalize_provider_protocol(value: Any) -> Any:
    # Configs persisted before the rename stored the protocol as "claude".
    if value == "claude":
        return "anthropic"
    return value


ModelProviderProtocol = Annotated[
    Literal["anthropic", "openai-compatible"],
    BeforeValidator(_normalize_provider_protocol),
]
ProviderRole = Literal[
    "generation",
    "repair",
    "activation-evaluation",
    "implementation-evaluation",
    "validation-explanation",
]
ProviderTestStatus = Literal["passed", "failed"]
ProviderFailureCategory = Literal[
    "auth-missing",
    "auth-failed",
    "url-error",
    "model-not-found",
    "protocol-mismatch",
    "timeout",
    "network-error",
    "unknown",
]
DangerLevel = Literal["low", "medium", "high"]
QualitySeverity = Literal[
    "security_blocker",
    "structure_blocker",
    "quality_error",
    "warning",
    "info",
]
QualitySource = Literal["validation", "activation", "implementation"]
InputControl = Literal["short-text", "long-text", "single-select", "multi-select"]
ConnectionStatusValue = Literal["unconfigured", "connecting", "connected", "disconnected", "error"]


MAX_CRITERION_SCORE = 4


class WorkflowStep(BaseModel):
    id: str = ""
    purpose: str = ""
    action: str = ""
    input: str = ""
    output: str = ""
    validation: str = ""
    failureHandling: str = ""


class PurposeInfo(BaseModel):
    usage: str = ""
    desiredOutcome: str = ""
    process: list[str] = Field(default_factory=list)
    completionCriteria: str = ""
    specialCases: str = ""


class KnowledgePitfall(BaseModel):
    id: str = ""
    description: str = ""
    goodExample: str = ""
    badExample: str = ""


class KnowledgeInfo(BaseModel):
    professionalInformation: list[str] = Field(default_factory=list)
    mandatoryRules: list[str] = Field(default_factory=list)
    pitfalls: list[KnowledgePitfall] = Field(default_factory=list)
    relatedSkills: list[str] = Field(default_factory=list)


class SupplementInfo(BaseModel):
    content: str = ""


class SkillDraft(BaseModel):
    id: str
    status: Literal["draft"] = "draft"
    name: str = ""
    displayName: str = ""
    targetPlatforms: list[TargetPlatform] = Field(default_factory=lambda: ["claude-code"])
    purpose: PurposeInfo = Field(default_factory=PurposeInfo)
    knowledge: KnowledgeInfo = Field(default_factory=KnowledgeInfo)
    supplement: SupplementInfo = Field(default_factory=SupplementInfo)
    createdAt: int | None = None
    updatedAt: int | None = None

    @field_validator("targetPlatforms")
    @classmethod
    def target_platforms_must_not_be_empty(cls, value: list[TargetPlatform]) -> list[TargetPlatform]:
        if not value:
            raise ValueError("targetPlatforms must not be empty")
        return value


class SkillBrief(BaseModel):
    skillName: str
    displayName: str
    targetUser: str = "solo workflow builder"
    usage: str
    desiredOutcome: str
    roughProcess: list[str] = Field(default_factory=list)
    completionCriteria: str
    specialCases: str = ""
    professionalInformation: list[str] = Field(default_factory=list)
    mandatoryRules: list[str] = Field(default_factory=list)
    pitfalls: list[KnowledgePitfall] = Field(default_factory=list)
    relatedSkills: list[str] = Field(default_factory=list)
    supplementalContext: str = ""
    targetPlatforms: list[TargetPlatform] = Field(default_factory=lambda: ["claude-code"])
    outputLanguage: OutputLanguage = "zh-CN"
    workflowSteps: list[WorkflowStep] = Field(default_factory=list)
    needsReferences: bool = False
    needsScripts: bool = False
    needsAssets: bool = False


class SkillMeta(BaseModel):
    name: str
    description: str
    language: OutputLanguage
    overview: str = ""


class SkillWorkflow(BaseModel):
    objective: str
    steps: list[WorkflowStep] = Field(default_factory=list)
    decisionPoints: list[str] = Field(default_factory=list)
    failureHandling: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)


class ReferenceFile(BaseModel):
    path: str
    purpose: str = ""
    content: str = ""


class ContextEngineering(BaseModel):
    filesystemAssumptions: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    referenceFiles: list[ReferenceFile] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)


class AgentKnowledge(BaseModel):
    unknownKnowledge: list[str] = Field(default_factory=list)
    pitfalls: list[KnowledgePitfall] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    counterExamples: list[str] = Field(default_factory=list)
    relatedSkills: list[str] = Field(default_factory=list)
    supplementalContext: str = ""


class SkillQuality(BaseModel):
    freedomLevel: FreedomLevel = "medium"
    hardRestrictions: list[str] = Field(default_factory=list)
    softGuidance: list[str] = Field(default_factory=list)
    validationChecklist: list[str] = Field(default_factory=list)


class SkillPlatforms(BaseModel):
    targets: list[TargetPlatform] = Field(default_factory=list)


class SkillIR(BaseModel):
    schemaVersion: str = "1.0"
    skill: SkillMeta
    workflow: SkillWorkflow
    contextEngineering: ContextEngineering = Field(default_factory=ContextEngineering)
    agentKnowledge: AgentKnowledge = Field(default_factory=AgentKnowledge)
    quality: SkillQuality = Field(default_factory=SkillQuality)
    platforms: SkillPlatforms


class FileNode(BaseModel):
    name: str
    type: Literal["file", "folder"]
    children: list["FileNode"] | None = None
    size: str | None = None


class ValidationItem(BaseModel):
    id: str
    ruleId: str
    level: ValidationLevel
    title: str
    description: str
    importance: str
    suggestion: str = ""
    blocksDownload: bool = False
    field: str | None = None
    inputLayer: InputLayer | None = None


class UserQuestion(BaseModel):
    issueId: str
    question: str
    inputControl: InputControl = "long-text"
    options: list[str] = Field(default_factory=list)
    existingAnswer: str | list[str] | None = None


class CriterionScore(BaseModel):
    criterion: str
    score: int = Field(ge=0, le=MAX_CRITERION_SCORE)
    reason: str
    evidence: list[str] = Field(default_factory=list)
    suggestion: str
    requiresUserInput: bool = False
    userQuestion: str | None = None
    inputControl: InputControl | None = None
    options: list[str] = Field(default_factory=list)


class QualityIssue(BaseModel):
    issueId: str
    source: QualitySource
    criterion: str
    severity: QualitySeverity
    score: float | None = None
    reason: str
    evidence: list[str] = Field(default_factory=list)
    suggestion: str
    affectedPaths: list[str] = Field(default_factory=list)
    autoFixable: bool = False
    requiresUserInput: bool = False
    userQuestion: str | None = None
    inputControl: InputControl | None = None
    options: list[str] = Field(default_factory=list)


class JudgeEvaluation(BaseModel):
    dimension: Literal["activation", "implementation"]
    criterionScores: list[CriterionScore] = Field(default_factory=list)
    dimensionScore: float = 0
    summary: str
    issues: list[QualityIssue] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    requiresRepair: bool = False
    requiresUserInput: bool = False
    userQuestions: list[UserQuestion] = Field(default_factory=list)

    @model_validator(mode="after")
    def recalculate_dimension_score(self) -> "JudgeEvaluation":
        expected = (
            {
                "specificity",
                "completeness",
                "trigger-term-quality",
                "distinctiveness-conflict-risk",
            }
            if self.dimension == "activation"
            else {
                "conciseness",
                "actionability",
                "workflow-clarity",
                "progressive-disclosure",
            }
        )
        actual = {item.criterion for item in self.criterionScores}
        if actual != expected or len(self.criterionScores) != 4:
            raise ValueError(
                f"{self.dimension} evaluation must contain exactly these criteria: "
                f"{', '.join(sorted(expected))}"
            )
        if self.criterionScores:
            self.dimensionScore = round(
                sum(item.score for item in self.criterionScores)
                / (len(self.criterionScores) * MAX_CRITERION_SCORE)
                * 100,
                2,
            )
        else:
            self.dimensionScore = 0
        if not self.requiresUserInput:
            # If any criterion requires user input, force the dimension to require it too
            self.requiresUserInput = any(item.requiresUserInput for item in self.criterionScores)
        return self


class QualityEvaluationReport(BaseModel):
    attemptId: str
    validationScore: float
    activationScore: float | None = None
    implementationScore: float | None = None
    overallScore: float | None = None
    passedStrictGate: bool = False
    passedDegradedGate: bool = False
    blockingIssueCount: int = 0
    issues: list[QualityIssue] = Field(default_factory=list)
    activation: JudgeEvaluation | None = None
    implementation: JudgeEvaluation | None = None
    rubricVersion: str
    evaluatedAt: int


class GenerationAttempt(BaseModel):
    id: str
    runId: str
    round: int = Field(ge=0, le=3)
    parentAttemptId: str | None = None
    skillIR: dict[str, Any] = Field(default_factory=dict)
    renderedPath: str
    isStructurallyValid: bool
    isSecuritySafe: bool
    changedPaths: list[str] = Field(default_factory=list)
    providerId: str | None = None
    modelName: str | None = None
    promptVersion: str = "1.0"
    inputIssueIds: list[str] = Field(default_factory=list)
    agentCalls: list["AgentCallMetadata"] = Field(default_factory=list)
    fileHashes: dict[str, str] = Field(default_factory=dict)
    skillIRSha256: str = ""
    activationSignature: str = ""
    implementationSignature: str = ""
    activationReusedFromAttemptId: str | None = None
    implementationReusedFromAttemptId: str | None = None
    durationMs: int = 0
    createdAt: int


class UserSupplement(BaseModel):
    id: str
    runId: str
    issueId: str
    question: str
    answer: str | list[str] | None = None
    skipped: bool = False
    mergedPaths: list[str] = Field(default_factory=list)
    createdAt: int


class RepairAgentResult(BaseModel):
    skillIR: SkillIR
    changedPaths: list[str] = Field(default_factory=list)
    resolvedIssueIds: list[str] = Field(default_factory=list)
    unresolvedIssues: list[str] = Field(default_factory=list)


class AgentCallMetadata(BaseModel):
    providerId: str
    providerRole: ProviderRole
    protocol: ModelProviderProtocol
    model: str
    promptVersion: str
    inputTokens: int = 0
    outputTokens: int = 0
    requests: int = 0
    durationMs: int = 0
    estimatedCostUsd: float | None = None


class SupplementAnswer(BaseModel):
    issueId: str
    answer: str | list[str]


class SupplementRequest(BaseModel):
    answers: list[SupplementAnswer] = Field(default_factory=list)
    skip: bool = False


class GenerationCreateRequest(BaseModel):
    draftId: str
    qualityMode: Literal["strict"] = "strict"
    maxRepairRounds: int = Field(default=3, ge=0, le=3)
    targetPlatforms: list[TargetPlatform] | None = None


class ModelConnectionProvider(BaseModel):
    id: str
    name: str
    model: str
    protocol: ModelProviderProtocol


class ModelConnectionStatus(BaseModel):
    status: ConnectionStatusValue
    generationProvider: ModelConnectionProvider | None = None
    judgeProvider: ModelConnectionProvider | None = None
    checkedAt: str | None = None
    message: str


class DownloadInfo(BaseModel):
    packageName: str
    version: str = "1.0.0"
    generatedAt: str
    platforms: list[str]
    fileCount: int
    size: str


class GenerationResult(BaseModel):
    id: str
    runId: str | None = None
    draftId: str
    status: GenerationStatus
    currentStage: GenerationStage | None
    progress: int
    files: list[FileNode] = Field(default_factory=list)
    skillMd: str = ""
    validation: list[ValidationItem] = Field(default_factory=list)
    blockingIssues: int = 0
    warnings: int = 0
    downloadInfo: DownloadInfo | None = None
    startedAt: int
    completedAt: int | None = None
    errorMessage: str | None = None
    modelProviderId: str | None = None
    modelProtocol: ModelProviderProtocol | None = None
    providerConnectionRisk: str | None = None
    artifactDir: str | None = None
    zipPath: str | None = None
    currentRound: int = 0
    maxRepairRounds: int = 3
    bestAttemptId: str | None = None
    finalAttemptId: str | None = None
    finalRound: int | None = None
    awaitingUserInputIssueIds: list[str] = Field(default_factory=list)
    promptedIssueIds: list[str] = Field(default_factory=list)
    userQuestions: list[UserQuestion] = Field(default_factory=list)
    qualityReport: QualityEvaluationReport | None = None
    qualityPolicyVersion: str = "1.0"
    promptBundleVersion: str = "1.0"
    failureCode: str | None = None
    normalizedBrief: dict[str, Any] = Field(default_factory=dict)
    finalSelectionReason: str | None = None
    artifactSha256: str | None = None
    targetPlatformsOverride: list[TargetPlatform] | None = None
    supplementScoreDelta: float | None = None

    @model_validator(mode="after")
    def set_run_id(self) -> "GenerationResult":
        if self.runId is None:
            self.runId = self.id
        return self


class PreviewResponse(BaseModel):
    files: list[FileNode]
    skillMd: str


class ValidationResponse(BaseModel):
    generationId: str
    items: list[ValidationItem]
    blockingIssues: int
    warnings: int


class HistoryItem(BaseModel):
    id: str
    generationId: str | None = None
    displayName: str
    name: str
    status: HistoryItemStatus
    platforms: list[str]
    createdAt: str
    updatedAt: str


_BLOCKED_ENV_NAMES = frozenset({"PATH", "HOME", "USER", "SHELL", "TERM", "LANG", "PWD", "OLDPWD", "EDITOR", "VISUAL", "HOSTNAME", "TMPDIR", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"})


class ApiKeyRef(BaseModel):
    type: Literal["env"] = "env"
    name: str

    @field_validator("name")
    @classmethod
    def key_name_must_be_environment_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or not cleaned.replace("_", "").isalnum() or cleaned[0].isdigit():
            raise ValueError("apiKeyRef.name must be an environment variable name")
        if cleaned in _BLOCKED_ENV_NAMES:
            raise ValueError(f"apiKeyRef.name cannot be a well-known environment variable: {cleaned}")
        return cleaned


class ProviderTestResult(BaseModel):
    status: ProviderTestStatus
    protocol: ModelProviderProtocol
    model: str
    latencyMs: int
    testedAt: str
    failureCategory: ProviderFailureCategory | None = None
    message: str


class ModelProviderBase(BaseModel):
    name: str
    protocol: ModelProviderProtocol
    baseUrl: str
    apiKeyRef: ApiKeyRef
    defaultModel: str
    roles: list[ProviderRole] = Field(default_factory=lambda: ["generation"])
    timeoutMs: int = 120000
    retries: int = 2
    inputPricePerMillionTokens: float = 0
    outputPricePerMillionTokens: float = 0
    streaming: bool = True
    customHeaders: dict[str, str] = Field(default_factory=dict)
    enabled: bool = True

    @field_validator("name", "defaultModel")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("value must not be empty")
        return cleaned

    @field_validator("baseUrl")
    @classmethod
    def base_url_must_be_http_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("baseUrl must be a valid http(s) URL")
        return cleaned

    @field_validator("roles")
    @classmethod
    def roles_must_not_be_empty(cls, value: list[ProviderRole]) -> list[ProviderRole]:
        if not value:
            raise ValueError("roles must not be empty")
        return list(dict.fromkeys(value))

    @field_validator("timeoutMs")
    @classmethod
    def timeout_must_be_positive(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("timeoutMs must be positive")
        return value

    @field_validator("retries")
    @classmethod
    def retries_must_be_bounded(cls, value: int) -> int:
        if value < 0 or value > 5:
            raise ValueError("retries must be between 0 and 5")
        return value

    @field_validator(
        "inputPricePerMillionTokens",
        "outputPricePerMillionTokens",
    )
    @classmethod
    def token_prices_must_not_be_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("token prices must not be negative")
        return value

    @field_validator("customHeaders")
    @classmethod
    def custom_headers_must_not_override_auth(cls, value: dict[str, str]) -> dict[str, str]:
        blocked = {"authorization", "x-api-key", "api-key", "bearer"}
        for header_name in value:
            if header_name.strip().lower() in blocked:
                raise ValueError("customHeaders must not override authentication headers")
        return {str(key): str(header_value) for key, header_value in value.items()}


class ModelProviderConfigCreate(ModelProviderBase):
    apiKey: str | None = None

    @field_validator("apiKey")
    @classmethod
    def api_key_must_be_single_line(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if "\n" in cleaned or "\r" in cleaned:
            raise ValueError("apiKey must be a single-line secret")
        return cleaned


class ModelProviderConfig(ModelProviderBase):
    id: str
    lastTest: ProviderTestResult | None = None


class ModelProviderConfigPatch(BaseModel):
    name: str | None = None
    protocol: ModelProviderProtocol | None = None
    baseUrl: str | None = None
    apiKeyRef: ApiKeyRef | None = None
    defaultModel: str | None = None
    roles: list[ProviderRole] | None = None
    timeoutMs: int | None = None
    retries: int | None = None
    inputPricePerMillionTokens: float | None = None
    outputPricePerMillionTokens: float | None = None
    streaming: bool | None = None
    customHeaders: dict[str, str] | None = None
    enabled: bool | None = None
    apiKey: str | None = None

    @field_validator(
        "inputPricePerMillionTokens",
        "outputPricePerMillionTokens",
    )
    @classmethod
    def token_prices_must_not_be_negative(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("token prices must not be negative")
        return value

    @field_validator("apiKey")
    @classmethod
    def api_key_must_be_single_line(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if "\n" in cleaned or "\r" in cleaned:
            raise ValueError("apiKey must be a single-line secret")
        return cleaned


class CliCommandSpec(BaseModel):
    name: str
    command: str
    purpose: str
    repeatable: bool
    reads: list[str] = Field(default_factory=list)
    writes: list[str] = Field(default_factory=list)
    requiresNetwork: bool = False
    dangerLevel: DangerLevel = "low"
    failureSummary: str


FileNode.model_rebuild()
GenerationAttempt.model_rebuild()


class AppSettings(BaseModel):
    defaultGenerateProvider: str = ""
    defaultRepairProvider: str = ""
    defaultValidateProvider: str = ""
    blockOnMissingConfig: bool = True
