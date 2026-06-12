import type { GenerationStage, SkillDraft } from '../types';

let idCounter = 100;
const uid = () => `draft_${Date.now()}_${++idCounter}`;

interface ProductStage {
  key: 'requirements' | 'workflow' | 'quality' | 'package';
  stages: GenerationStage[];
  label: string;
  sub: string;
}

export const STAGES: ProductStage[] = [
  {
    key: 'requirements',
    stages: ['queued', 'normalizing', 'injecting-rules'],
    label: '理解需求',
    sub: '整理必要输入并补全标准规格',
  },
  {
    key: 'workflow',
    stages: ['generating-workflow', 'splitting-workflow', 'generating-ir', 'validating-schema'],
    label: '构建工作流',
    sub: '设计步骤、输入输出、校验和失败处理',
  },
  {
    key: 'quality',
    stages: ['generating-knowledge', 'generating-quality'],
    label: '补全知识与质量',
    sub: '补充专业知识、约束和验收标准',
  },
  {
    key: 'package',
    stages: [
      'generating-trace',
      'rendering-files',
      'running-validation-checks',
      'evaluating-activation',
      'evaluating-implementation',
      'aggregating-scores',
      'repairing',
      'awaiting-user-input',
      'selecting-best-candidate',
      'quality-gate',
      'packaging',
    ],
    label: '检查与打包',
    sub: '持续评测优化，选择最佳版本并生成文件',
  },
];

export function createBlankDraft(): SkillDraft {
  const now = Date.now();

  return {
    id: uid(),
    name: '',
    displayName: '',
    targetPlatforms: ['claude-code'],
    purpose: {
      usage: '',
      desiredOutcome: '',
      process: [],
      completionCriteria: '',
      specialCases: '',
    },
    knowledge: {
      professionalInformation: [],
      mandatoryRules: [],
      pitfalls: [],
      relatedSkills: [],
    },
    supplement: { content: '' },
    createdAt: now,
    updatedAt: now,
  };
}

export const PLATFORMS = [
  { value: 'claude-code' as const, label: 'Claude Code' },
  { value: 'codex' as const, label: 'Codex' },
  { value: 'hermes-openclaw' as const, label: 'Hermes / OpenClaw' },
];

export const STEP_KEYS = [
  'basic',
  'purpose',
  'knowledge',
  'supplement',
] as const;

export type StepKey = (typeof STEP_KEYS)[number];

export const STEP_LABELS: Record<StepKey, string> = {
  basic: '基础信息',
  purpose: '用途与流程',
  knowledge: '知识、规则与依赖',
  supplement: '补充说明',
};

export const STEP_COMPLETION_WEIGHTS: Record<StepKey, (draft: SkillDraft) => number> = {
  basic: (draft) => {
    let score = 0;
    if (draft.displayName) score += 60;
    if (draft.targetPlatforms.length > 0) score += 40;
    return score;
  },
  purpose: (draft) => {
    let score = 0;
    if (draft.purpose.usage.trim()) score += 50;
    if (draft.purpose.desiredOutcome.trim()) score += 50;
    return score;
  },
  // 知识步骤全部为可选推荐项，不计入必填完成度。
  knowledge: () => 100,
  supplement: () => 100,
};

export const PROVIDER_PROTOCOLS = [
  { value: 'anthropic' as const, label: 'Anthropic 协议', desc: 'Anthropic Messages API（Claude 系列模型）' },
  { value: 'openai-compatible' as const, label: 'OpenAI-compatible 协议', desc: '兼容 OpenAI Chat Completions 格式的 API（如 OpenAI、DeepSeek、Ollama、vLLM）' },
];

// 各协议的推荐默认值；仅在对应字段仍是默认值/为空时随协议切换自动替换。
export const PROTOCOL_DEFAULTS = {
  anthropic: {
    baseUrl: 'https://api.anthropic.com',
    keyEnv: 'ANTHROPIC_API_KEY',
    model: 'claude-sonnet-4-6',
  },
  'openai-compatible': {
    baseUrl: '',
    keyEnv: 'OPENAI_API_KEY',
    model: '',
  },
} as const;

export const LLM_PROVIDER_PRESETS = [
  {
    label: 'Anthropic Claude',
    protocol: 'anthropic' as const,
    baseUrl: 'https://api.anthropic.com',
    model: 'claude-sonnet-4-6',
    keyEnv: 'ANTHROPIC_API_KEY',
    models: ['claude-sonnet-4-6', 'claude-opus-4-8', 'claude-fable-5', 'claude-haiku-4-5'],
  },
  {
    label: 'OpenAI',
    protocol: 'openai-compatible' as const,
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-5.4',
    keyEnv: 'OPENAI_API_KEY',
    models: ['gpt-5.5', 'gpt-5.4', 'gpt-5.4-mini'],
  },
  {
    label: 'DeepSeek',
    protocol: 'openai-compatible' as const,
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-v4-flash',
    keyEnv: 'DEEPSEEK_API_KEY',
    models: ['deepseek-v4-flash', 'deepseek-v4-pro'],
  },
  {
    label: 'OpenRouter',
    protocol: 'openai-compatible' as const,
    baseUrl: 'https://openrouter.ai/api/v1',
    model: 'openrouter/auto',
    keyEnv: 'OPENROUTER_API_KEY',
    models: ['openrouter/auto'],
  },
  {
    label: '本地 Ollama',
    protocol: 'openai-compatible' as const,
    baseUrl: 'http://localhost:11434',
    model: '',
    keyEnv: 'OLLAMA_API_KEY',
    models: [],
  },
];
