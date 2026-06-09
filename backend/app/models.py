from __future__ import annotations

from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


TargetPlatform = Literal["claude-code", "codex", "hermes-openclaw"]
SkillType = Literal["automation", "workflow", "template", "constraint"]
OutputLanguage = Literal["zh-CN", "en"]
FreedomLevel = Literal["high", "medium", "low"]
ValidationStrictness = Literal["loose", "normal", "strict"]
GenerationStage = Literal[
    "normalizing",
    "injecting-rules",
    "splitting-workflow",
    "generating-ir",
    "rendering-files",
    "quality-gate",
    "packaging",
]
GenerationStatus = Literal["idle", "generating", "validating", "success", "failed"]
ValidationLevel = Literal["pass", "warning", "blocking"]
HistoryItemStatus = Literal["draft", "generating", "validating", "downloadable", "failed"]
ModelProviderProtocol = Literal["claude", "openai-compatible"]
ProviderRole = Literal["generation", "repair", "validation-explanation"]
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


class TriggerInfo(BaseModel):
    intent: str = ""
    taskType: str = ""
    positiveExamples: list[str] = Field(default_factory=list)
    negativeExamples: list[str] = Field(default_factory=list)
    commonPhrases: list[str] = Field(default_factory=list)
    relatedFileTypes: list[str] = Field(default_factory=list)
    relatedTools: list[str] = Field(default_factory=list)
    relatedObjects: list[str] = Field(default_factory=list)


class WorkflowStep(BaseModel):
    id: str = ""
    purpose: str = ""
    action: str = ""
    input: str = ""
    output: str = ""
    validation: str = ""
    failureHandling: str = ""


class WorkflowInfo(BaseModel):
    objective: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    preconditions: str = ""


class ContextInfo(BaseModel):
    filesToRead: list[str] = Field(default_factory=list)
    needsReferences: bool = False
    needsScripts: bool = False
    needsAssets: bool = False
    loadingRule: str = ""


class KnowledgePitfall(BaseModel):
    id: str = ""
    description: str = ""
    goodExample: str = ""
    badExample: str = ""


class KnowledgeInfo(BaseModel):
    industryRules: list[str] = Field(default_factory=list)
    internalProcesses: list[str] = Field(default_factory=list)
    personalExperience: list[str] = Field(default_factory=list)
    pitfalls: list[KnowledgePitfall] = Field(default_factory=list)


class OutputControl(BaseModel):
    freedom: FreedomLevel = "medium"
    allowHardLimits: bool = True
    validationStrictness: ValidationStrictness = "normal"
    generateInstallGuide: bool = True
    allowDownloadWithWarnings: bool = False


class ChatMessage(BaseModel):
    id: str = ""
    role: Literal["user", "agent"] = "user"
    content: str = ""
    timestamp: int = 0


class SupplementInfo(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class SkillDraft(BaseModel):
    id: str
    status: Literal["draft"] = "draft"
    name: str = ""
    displayName: str = ""
    language: OutputLanguage = "zh-CN"
    skillType: SkillType = "workflow"
    targetPlatforms: list[TargetPlatform] = Field(default_factory=lambda: ["claude-code"])
    trigger: TriggerInfo = Field(default_factory=TriggerInfo)
    workflow: WorkflowInfo = Field(default_factory=WorkflowInfo)
    context: ContextInfo = Field(default_factory=ContextInfo)
    knowledge: KnowledgeInfo = Field(default_factory=KnowledgeInfo)
    outputControl: OutputControl = Field(default_factory=OutputControl)
    supplement: SupplementInfo = Field(default_factory=SupplementInfo)
    createdAt: int
    updatedAt: int

    @field_validator("targetPlatforms")
    @classmethod
    def target_platforms_must_not_be_empty(cls, value: list[TargetPlatform]) -> list[TargetPlatform]:
        return value or ["claude-code"]


class SkillDraftCreate(BaseModel):
    id: str | None = None
    name: str = ""
    displayName: str = ""
    language: OutputLanguage = "zh-CN"
    skillType: SkillType = "workflow"
    targetPlatforms: list[TargetPlatform] = Field(default_factory=lambda: ["claude-code"])
    trigger: TriggerInfo = Field(default_factory=TriggerInfo)
    workflow: WorkflowInfo = Field(default_factory=WorkflowInfo)
    context: ContextInfo = Field(default_factory=ContextInfo)
    knowledge: KnowledgeInfo = Field(default_factory=KnowledgeInfo)
    outputControl: OutputControl = Field(default_factory=OutputControl)
    supplement: SupplementInfo = Field(default_factory=SupplementInfo)
    createdAt: int | None = None
    updatedAt: int | None = None


class SkillBrief(BaseModel):
    skillName: str
    displayName: str
    targetUser: str = "solo workflow builder"
    triggerIntent: str
    taskType: str
    positiveExamples: list[str] = Field(default_factory=list)
    antiTriggers: list[str] = Field(default_factory=list)
    commonPhrases: list[str] = Field(default_factory=list)
    workflowObjective: str
    workflowSteps: list[WorkflowStep] = Field(default_factory=list)
    preconditions: str = ""
    contextFiles: list[str] = Field(default_factory=list)
    needsReferences: bool = False
    needsScripts: bool = False
    needsAssets: bool = False
    loadingRule: str = ""
    unknownKnowledge: list[str] = Field(default_factory=list)
    pitfalls: list[KnowledgePitfall] = Field(default_factory=list)
    targetPlatforms: list[TargetPlatform] = Field(default_factory=list)
    outputLanguage: OutputLanguage = "zh-CN"
    freedomLevel: FreedomLevel = "medium"
    allowHardLimits: bool = True
    validationStrictness: ValidationStrictness = "normal"
    allowDownloadWithWarnings: bool = False


class SkillMeta(BaseModel):
    name: str
    description: str
    language: OutputLanguage


class SkillWorkflow(BaseModel):
    objective: str
    steps: list[WorkflowStep] = Field(default_factory=list)
    decisionPoints: list[str] = Field(default_factory=list)
    failureHandling: list[str] = Field(default_factory=list)
    verification: list[str] = Field(default_factory=list)


class ContextEngineering(BaseModel):
    filesystemAssumptions: list[str] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)


class AgentKnowledge(BaseModel):
    unknownKnowledge: list[str] = Field(default_factory=list)
    pitfalls: list[KnowledgePitfall] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)
    counterExamples: list[str] = Field(default_factory=list)


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


class DownloadInfo(BaseModel):
    packageName: str
    version: str = "1.0.0"
    generatedAt: str
    platforms: list[str]
    fileCount: int
    size: str


class GenerationResult(BaseModel):
    id: str
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
    displayName: str
    name: str
    status: HistoryItemStatus
    platforms: list[str]
    createdAt: str
    updatedAt: str


class ApiKeyRef(BaseModel):
    type: Literal["env"] = "env"
    name: str

    @field_validator("name")
    @classmethod
    def key_name_must_be_environment_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned or not cleaned.replace("_", "").isalnum() or cleaned[0].isdigit():
            raise ValueError("apiKeyRef.name must be an environment variable name")
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
    streaming: bool | None = None
    customHeaders: dict[str, str] | None = None
    enabled: bool | None = None
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
