import type { SkillDraft } from '../types';

let idCounter = 100;
const uid = () => `draft_${Date.now()}_${++idCounter}`;

export const STAGES = [
  { key: 'normalizing' as const, label: '输入归一化', sub: '标准化表单和聊天内容' },
  { key: 'injecting-rules' as const, label: '注入规则', sub: '加载质量规则和易错点' },
  { key: 'splitting-workflow' as const, label: '工作流拆解', sub: '划分步骤和分支逻辑' },
  { key: 'generating-ir' as const, label: '生成 Skill IR', sub: '创建中间表示' },
  { key: 'rendering-files' as const, label: '渲染文件', sub: '输出 SKILL.md 和辅助文件' },
  { key: 'quality-gate' as const, label: '质量校验', sub: '运行规则校验器' },
  { key: 'packaging' as const, label: 'zip 打包', sub: '压缩为可下载包' },
];

export function createBlankDraft(): SkillDraft {
  const now = Date.now();

  return {
    id: uid(),
    name: '',
    displayName: '',
    language: 'zh-CN',
    skillType: 'workflow',
    targetPlatforms: ['claude-code'],
    trigger: {
      intent: '',
      taskType: '',
      positiveExamples: [],
      negativeExamples: [],
      commonPhrases: [],
      relatedFileTypes: [],
      relatedTools: [],
      relatedObjects: [],
    },
    workflow: {
      objective: '',
      steps: [],
      preconditions: '',
    },
    context: {
      filesToRead: [],
      needsReferences: false,
      needsScripts: false,
      needsAssets: false,
      loadingRule: '',
    },
    knowledge: {
      industryRules: [],
      internalProcesses: [],
      personalExperience: [],
      pitfalls: [],
    },
    outputControl: {
      freedom: 'medium',
      allowHardLimits: true,
      validationStrictness: 'normal',
      generateInstallGuide: true,
      allowDownloadWithWarnings: false,
    },
    supplement: { messages: [] },
    createdAt: now,
    updatedAt: now,
  };
}

export const PLATFORMS = [
  { value: 'claude-code' as const, label: 'Claude Code' },
  { value: 'codex' as const, label: 'Codex' },
  { value: 'hermes-openclaw' as const, label: 'Hermes / OpenClaw' },
];

export const SKILL_TYPES = [
  { value: 'automation' as const, label: '自动化任务' },
  { value: 'workflow' as const, label: '工作流' },
  { value: 'template' as const, label: '模板' },
  { value: 'constraint' as const, label: '约束规则' },
];

export const FREEDOM_LEVELS = [
  { value: 'high' as const, label: '高自由度', desc: 'Agent 可以灵活发挥' },
  { value: 'medium' as const, label: '中等自由度', desc: '遵循流程但可微调' },
  { value: 'low' as const, label: '低自由度', desc: '严格按步骤执行' },
];

export const VALIDATION_LEVELS = [
  { value: 'loose' as const, label: '宽松', desc: '只检查必要项' },
  { value: 'normal' as const, label: '正常', desc: '标准校验规则' },
  { value: 'strict' as const, label: '严格', desc: '全面深度校验' },
];

export const STEP_KEYS = [
  'basic',
  'trigger',
  'workflow',
  'context',
  'knowledge',
  'output',
  'supplement',
] as const;

export type StepKey = (typeof STEP_KEYS)[number];

export const STEP_LABELS: Record<StepKey, string> = {
  basic: '基础信息',
  trigger: '触发条件',
  workflow: '工作流',
  context: '文件上下文',
  knowledge: '经验知识',
  output: '输出控制',
  supplement: '聊天补充',
};

export const STEP_COMPLETION_WEIGHTS: Record<StepKey, (draft: SkillDraft) => number> = {
  basic: (draft) => {
    let score = 0;
    if (draft.displayName) score += 40;
    if (draft.name) score += 30;
    if (draft.targetPlatforms.length > 0) score += 30;
    return score;
  },
  trigger: (draft) => {
    let score = 0;
    if (draft.trigger.intent) score += 25;
    if (draft.trigger.taskType) score += 25;
    if (draft.trigger.positiveExamples.length > 0) score += 25;
    if (draft.trigger.negativeExamples.length > 0) score += 25;
    return score;
  },
  workflow: (draft) => {
    if (draft.workflow.steps.length === 0) return 0;
    return Math.min(100, (draft.workflow.steps.length / 2) * 50 + (draft.workflow.objective ? 50 : 0));
  },
  context: () => 60,
  knowledge: (draft) => {
    let score = 30;
    if (draft.knowledge.pitfalls.length > 0) score += 40;
    if (draft.knowledge.industryRules.length > 0) score += 30;
    return Math.min(100, score);
  },
  output: () => 100,
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
    model: 'claude-sonnet-4-20250514',
    keyEnv: 'ANTHROPIC_API_KEY',
    models: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-haiku-4-20250514'],
  },
  {
    label: 'OpenAI',
    protocol: 'openai-compatible' as const,
    baseUrl: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    keyEnv: 'OPENAI_API_KEY',
    models: ['gpt-4o', 'gpt-4o-mini', 'o3', 'o4-mini'],
  },
  {
    label: 'DeepSeek',
    protocol: 'openai-compatible' as const,
    baseUrl: 'https://api.deepseek.com',
    model: 'deepseek-chat',
    keyEnv: 'DEEPSEEK_API_KEY',
    models: ['deepseek-chat', 'deepseek-reasoner'],
  },
  {
    label: 'OpenRouter',
    protocol: 'openai-compatible' as const,
    baseUrl: 'https://openrouter.ai/api/v1',
    model: 'anthropic/claude-sonnet-4',
    keyEnv: 'OPENROUTER_API_KEY',
    models: ['anthropic/claude-sonnet-4', 'openai/gpt-4o', 'deepseek/deepseek-chat'],
  },
  {
    label: '本地 Ollama',
    protocol: 'openai-compatible' as const,
    baseUrl: 'http://localhost:11434',
    model: 'llama3',
    keyEnv: 'OLLAMA_API_KEY',
    models: ['llama3', 'qwen2.5', 'deepseek-r1'],
  },
];
