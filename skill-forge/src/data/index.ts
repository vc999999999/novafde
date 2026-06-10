import type { SkillDraft } from '../types';

let idCounter = 100;
const uid = () => `draft_${Date.now()}_${++idCounter}`;

export const STAGES = [
  { key: 'queued' as const, label: '准备任务', sub: '创建本地生成记录' },
  { key: 'normalizing' as const, label: '整理输入', sub: '归一化表单与补充信息' },
  { key: 'injecting-rules' as const, label: '注入规则', sub: '将质量规则注入生成上下文' },
  { key: 'splitting-workflow' as const, label: '拆分工作流', sub: '将复杂流程拆分为可执行步骤' },
  { key: 'generating-ir' as const, label: '生成 Skill IR', sub: 'PydanticAI 生成结构化候选' },
  { key: 'running-validation-checks' as const, label: '结构校验', sub: '检查规范、路径与强制规则' },
  { key: 'evaluating-activation' as const, label: '触发评测', sub: '评估描述的触发准确性' },
  { key: 'evaluating-implementation' as const, label: '实现评测', sub: '评估工作流可执行性' },
  { key: 'aggregating-scores' as const, label: '汇总评分', sub: '计算质量门禁与修复方向' },
  { key: 'quality-gate' as const, label: '质量门禁', sub: '检查是否通过质量门禁' },
  { key: 'repairing' as const, label: '定向优化', sub: '仅修复未通过的内容' },
  { key: 'selecting-best-candidate' as const, label: '选择版本', sub: '选择历史最高分安全候选' },
  { key: 'packaging' as const, label: '打包文件', sub: '生成可下载 zip' },
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
    if (draft.purpose.usage.trim()) score += 20;
    if (draft.purpose.desiredOutcome.trim()) score += 20;
    if (draft.purpose.process.some((item) => item.trim())) score += 30;
    if (draft.purpose.completionCriteria.trim()) score += 30;
    return score;
  },
  knowledge: (draft) => {
    let score = 0;
    if (draft.knowledge.professionalInformation.length > 0) score += 34;
    if (draft.knowledge.mandatoryRules.length > 0) score += 33;
    if (draft.knowledge.pitfalls.some((pitfall) =>
      pitfall.description.trim() && pitfall.goodExample.trim() && pitfall.badExample.trim()
    )) score += 33;
    return score;
  },
  supplement: () => 100,
};

export const PROVIDER_PROTOCOLS = [
  { value: 'claude' as const, label: 'Claude 协议', desc: 'Anthropic Claude API v1/v2' },
  { value: 'openai-compatible' as const, label: 'OpenAI-compatible 协议', desc: '兼容 OpenAI 格式的 API（如 Ollama、vLLM）' },
];

export const LLM_PROVIDER_PRESETS = [
  {
    label: 'Anthropic Claude',
    protocol: 'claude' as const,
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
