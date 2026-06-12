import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import PageHeader from '../components/PageHeader';
import Toggle from '../components/Toggle';
import {
  createModelProvider,
  deleteModelProvider,
  getSettings,
  listModelProviders,
  saveSettings,
  testModelProvider,
  updateModelProvider,
} from '../api';
import { LLM_PROVIDER_PRESETS, PROTOCOL_DEFAULTS, PROVIDER_PROTOCOLS } from '../data';
import type {
  ApiKeyRef,
  AppSettings,
  ConnectionTestResult,
  ModelProviderConfig,
  ModelProviderPayload,
  ProviderProtocol,
  ProviderTestResult,
} from '../types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { NativeSelect } from '@/components/ui/native-select';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

type ProviderForm = ModelProviderConfig & {
  apiKey: string;
};

let providerIdCounter = 10;
const newDraftProviderId = () => `draft_provider_${++providerIdCounter}`;

const emptyProvider = (protocol: ProviderProtocol = 'anthropic'): ModelProviderConfig => ({
  id: newDraftProviderId(),
  name: '',
  protocol,
  baseUrl: PROTOCOL_DEFAULTS[protocol].baseUrl,
  apiKeyRef: { type: 'env', name: PROTOCOL_DEFAULTS[protocol].keyEnv },
  defaultModel: PROTOCOL_DEFAULTS[protocol].model,
  roles: [
    'generation',
    'repair',
    'activation-evaluation',
    'implementation-evaluation',
  ],
  timeoutMs: 120000,
  retries: 2,
  inputPricePerMillionTokens: 0,
  outputPricePerMillionTokens: 0,
  streaming: true,
  customHeaders: {},
  enabled: true,
  lastTest: null,
});

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败，请检查后端服务。';
}

function toPayload(provider: ProviderForm): ModelProviderPayload {
  const payload: ModelProviderPayload = {
    name: provider.name,
    protocol: provider.protocol,
    baseUrl: provider.baseUrl,
    apiKeyRef: provider.apiKeyRef,
    defaultModel: provider.defaultModel,
    roles: provider.roles,
    timeoutMs: provider.timeoutMs,
    retries: provider.retries,
    inputPricePerMillionTokens: provider.inputPricePerMillionTokens,
    outputPricePerMillionTokens: provider.outputPricePerMillionTokens,
    streaming: provider.streaming,
    customHeaders: provider.customHeaders,
    enabled: provider.enabled,
  };
  if (provider.apiKey.trim()) {
    payload.apiKey = provider.apiKey.trim();
  }
  return payload;
}

function toConnectionResult(result: ProviderTestResult): ConnectionTestResult {
  if (result.status === 'passed') {
    return {
      status: 'success',
      protocol: result.protocol,
      modelId: result.model,
      latencyMs: result.latencyMs,
    };
  }

  const categoryMap: Record<NonNullable<ProviderTestResult['failureCategory']>, NonNullable<ConnectionTestResult['errorCategory']>> = {
    'auth-missing': 'missing_key',
    'auth-failed': 'auth_failed',
    'url-error': 'bad_url',
    'model-not-found': 'model_not_found',
    'protocol-mismatch': 'protocol_mismatch',
    timeout: 'timeout',
    'network-error': 'unknown',
    unknown: 'unknown',
  };

  return {
    status: 'error',
    protocol: result.protocol,
    modelId: result.model,
    latencyMs: result.latencyMs,
    errorCategory: categoryMap[result.failureCategory ?? 'unknown'],
    errorMessage: result.message,
  };
}

function TestBadge({ result }: { result: ConnectionTestResult }) {
  if (result.status === 'idle') return null;
  if (result.status === 'testing') {
    return <Badge className="bg-accent-dim text-accent border border-accent-border gap-1.5 text-[11px] tracking-widest uppercase"><span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />测试中</Badge>;
  }
  if (result.status === 'success') {
    return <Badge className="bg-success-dim text-success border border-success-border gap-1.5 text-[11px] tracking-widest uppercase"><span className="w-1.5 h-1.5 rounded-full bg-success" />连接成功 · {result.latencyMs}ms</Badge>;
  }

  const errorLabels: Record<string, string> = {
    missing_key: '缺少 API Key',
    auth_failed: '鉴权失败',
    bad_url: 'URL 不可达',
    model_not_found: '模型不存在',
    protocol_mismatch: '协议不匹配',
    timeout: '连接超时',
    unknown: '未知错误',
  };

  return <Badge variant="destructive" className="bg-error-dim text-error border border-error-border gap-1.5 text-[11px] tracking-widest uppercase"><span className="w-1.5 h-1.5 rounded-full bg-error" />{errorLabels[result.errorCategory ?? 'unknown'] || '连接失败'}</Badge>;
}

function ProviderEditor({
  provider,
  persisted,
  onSave,
  onCancel,
  onTest,
  testResult,
  saving,
}: {
  provider: ModelProviderConfig;
  persisted: boolean;
  onSave: (provider: ProviderForm) => void;
  onCancel: () => void;
  onTest: (id: string) => void;
  testResult: ConnectionTestResult;
  saving: boolean;
}) {
  const [form, setForm] = useState<ProviderForm>({ ...provider, apiKey: '' });
  const [showApiKey, setShowApiKey] = useState(false);
  // 预设选择是显式状态：手动修改 Base URL 等字段不会让下拉框自己跳走。
  const [presetIndex, setPresetIndex] = useState<number>(() =>
    LLM_PROVIDER_PRESETS.findIndex(
      (preset) => preset.protocol === provider.protocol && preset.baseUrl === provider.baseUrl,
    ),
  );
  const selectedPreset =
    presetIndex >= 0 && LLM_PROVIDER_PRESETS[presetIndex]?.protocol === form.protocol
      ? LLM_PROVIDER_PRESETS[presetIndex]
      : undefined;
  const modelOptions = selectedPreset?.models ?? [];
  const isCustomModel = Boolean(form.defaultModel) && !modelOptions.includes(form.defaultModel);

  const set = <K extends keyof ProviderForm>(key: K, val: ProviderForm[K]) =>
    setForm((prev) => ({ ...prev, [key]: val }));

  const setApiKeyRef = (updates: Partial<ApiKeyRef>) =>
    setForm((prev) => ({
      ...prev,
      apiKeyRef: { ...prev.apiKeyRef, ...updates },
    }));

  return (
    <Card className="bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
      <div className="grid gap-4 grid-cols-1 md:grid-cols-2 [&>*]:space-y-1.5">
        <div className="md:col-span-2">
          <Label className="text-muted-foreground">Quick fill Provider</Label>
          <NativeSelect
            value={selectedPreset ? String(presetIndex) : ''}
            onChange={(event) => {
              if (event.target.value === '') {
                setPresetIndex(-1);
                return;
              }
              const index = Number(event.target.value);
              const preset = LLM_PROVIDER_PRESETS[index];
              if (!preset) return;
              setPresetIndex(index);
              setForm((prev) => ({
                ...prev,
                name: prev.name.trim() ? prev.name : preset.label,
                protocol: preset.protocol,
                baseUrl: preset.baseUrl,
                defaultModel: preset.model,
                apiKeyRef: { type: 'env', name: preset.keyEnv },
              }));
            }}
          >
            <option value="">Custom provider</option>
            {LLM_PROVIDER_PRESETS.map((preset, index) => (
              <option key={`${preset.label}-${preset.protocol}`} value={index}>{preset.label}</option>
            ))}
          </NativeSelect>
          <p className="text-xs text-muted-foreground mt-1 leading-snug">选择常用 Provider 后会自动填入协议、Base URL、模型和本地环境变量名。</p>
        </div>

        <div className="md:col-span-2">
          <Label className="text-muted-foreground">Provider 名称</Label>
          <Input value={form.name} onChange={(e) => set('name', e.target.value)} placeholder="My Claude API" />
        </div>

        <div>
          <Label className="text-muted-foreground">协议</Label>
          <NativeSelect
            value={form.protocol}
            onChange={(event) => {
              const protocol = event.target.value as ProviderProtocol;
              setForm((prev) => {
                if (prev.protocol === protocol) return prev;
                const prevDefaults = PROTOCOL_DEFAULTS[prev.protocol];
                const nextDefaults = PROTOCOL_DEFAULTS[protocol];
                const preset = presetIndex >= 0 ? LLM_PROVIDER_PRESETS[presetIndex] : undefined;
                // 仅当字段还是旧协议/预设的默认值（或为空）时跟随协议切换，避免清掉用户已填内容。
                const carry = (current: string, defaults: string[], nextDefault: string) =>
                  !current.trim() || defaults.includes(current) ? nextDefault : current;
                return {
                  ...prev,
                  protocol,
                  baseUrl: carry(
                    prev.baseUrl,
                    [prevDefaults.baseUrl, preset?.baseUrl ?? ''],
                    nextDefaults.baseUrl,
                  ),
                  defaultModel: carry(
                    prev.defaultModel,
                    [prevDefaults.model, preset?.model ?? '', ...(preset?.models ?? [])],
                    nextDefaults.model,
                  ),
                  apiKeyRef: {
                    ...prev.apiKeyRef,
                    name: carry(
                      prev.apiKeyRef.name,
                      [prevDefaults.keyEnv, preset?.keyEnv ?? ''],
                      nextDefaults.keyEnv,
                    ),
                  },
                };
              });
            }}
          >
            {PROVIDER_PROTOCOLS.map((protocol) => (
              <option key={protocol.value} value={protocol.value}>{protocol.label}</option>
            ))}
          </NativeSelect>
          <p className="text-xs text-muted-foreground mt-1 leading-snug">
            {PROVIDER_PROTOCOLS.find((protocol) => protocol.value === form.protocol)?.desc}
          </p>
        </div>

        <div>
          <Label className="text-muted-foreground">API Key</Label>
          <div className="flex gap-2">
            <Input
              type={showApiKey ? 'text' : 'password'}
              value={form.apiKey}
              onChange={(e) => set('apiKey', e.target.value)}
              placeholder={persisted ? '留空则沿用已保存 key' : 'sk-...'}
              autoComplete="off"
              className="flex-1"
            />
            <Button variant="outline" size="sm" onClick={() => setShowApiKey((v) => !v)} type="button">
              {showApiKey ? '隐藏' : '显示'}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground mt-1 leading-snug">优先保存到系统钥匙串；不可用时写入本地加密密钥库。后端响应不会返回明文。</p>
        </div>

        <div>
          <Label className="text-muted-foreground">模型</Label>
          {modelOptions.length > 0 ? (
            <NativeSelect
              value={isCustomModel || !form.defaultModel ? '__custom__' : form.defaultModel}
              onChange={(event) => {
                if (event.target.value === '__custom__') {
                  set('defaultModel', '');
                  return;
                }
                set('defaultModel', event.target.value);
              }}
            >
              {modelOptions.map((model) => (
                <option key={model} value={model}>{model}</option>
              ))}
              <option value="__custom__">自定义模型</option>
            </NativeSelect>
          ) : (
            <Input
              value={form.defaultModel}
              onChange={(e) => set('defaultModel', e.target.value)}
              placeholder={form.protocol === 'anthropic' ? 'claude-sonnet-4-6' : '输入 Provider 支持的模型 ID'}
            />
          )}
        </div>

        {(isCustomModel || (modelOptions.length > 0 && !form.defaultModel)) && (
          <div>
            <Label className="text-muted-foreground">自定义模型 ID</Label>
            <Input
              value={form.defaultModel}
              onChange={(e) => set('defaultModel', e.target.value)}
              placeholder="输入 Provider 支持的模型 ID"
            />
          </div>
        )}

        <div>
          <Label className="text-muted-foreground">Base URL</Label>
          <Input value={form.baseUrl} onChange={(e) => set('baseUrl', e.target.value)} placeholder="https://api.anthropic.com" />
        </div>

        <div>
          <Label className="text-muted-foreground">密钥引用名称</Label>
          <Input value={form.apiKeyRef.name} onChange={(e) => setApiKeyRef({ name: e.target.value })} placeholder="ANTHROPIC_API_KEY" />
          <p className="text-xs text-muted-foreground mt-1 leading-snug">仅作为本地钥匙串或加密密钥库中的索引名称。</p>
        </div>

        <div>
          <Label className="text-muted-foreground">超时 (ms)</Label>
          <Input type="number" value={form.timeoutMs} onChange={(e) => set('timeoutMs', Number(e.target.value))} min={5000} step={5000} />
        </div>

        <div>
          <Label className="text-muted-foreground">重试次数</Label>
          <Input type="number" value={form.retries} onChange={(e) => set('retries', Number(e.target.value))} min={0} max={5} />
        </div>

        <div>
          <Label className="text-muted-foreground">输入价格 (USD / 1M tokens)</Label>
          <Input
            type="number"
            value={form.inputPricePerMillionTokens}
            onChange={(e) => set('inputPricePerMillionTokens', Number(e.target.value))}
            min={0}
            step={0.01}
          />
        </div>

        <div>
          <Label className="text-muted-foreground">输出价格 (USD / 1M tokens)</Label>
          <Input
            type="number"
            value={form.outputPricePerMillionTokens}
            onChange={(e) => set('outputPricePerMillionTokens', Number(e.target.value))}
            min={0}
            step={0.01}
          />
          <p className="mt-1 text-xs leading-snug text-muted-foreground">
            可留 0 表示未知；填写后用于本地成本统计和单任务成本上限。
          </p>
        </div>

        <div>
          <Label className="text-muted-foreground">启用流式返回</Label>
          <div className="mt-2">
            <Switch checked={form.streaming} onCheckedChange={(checked) => set('streaming', checked)} />
          </div>
        </div>

        <div>
          <Label className="text-muted-foreground">启用 Provider</Label>
          <div className="mt-2">
            <Switch checked={form.enabled} onCheckedChange={(checked) => set('enabled', checked)} />
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 mt-5 pt-4 border-t border-panel-border">
        <Button
          variant="outline"
          onClick={() => onTest(form.id)}
          type="button"
          disabled={!persisted || testResult.status === 'testing'}
        >
          {!persisted ? '保存后测试' : testResult.status === 'testing' ? '测试中...' : '测试连接'}
        </Button>
        <TestBadge result={testResult} />
        {testResult.status === 'error' && testResult.errorMessage && (
          <span className="text-xs text-destructive m-0">{testResult.errorMessage}</span>
        )}
      </div>

      <div className="flex justify-between items-center mt-auto pt-4 border-t border-panel-border">
        <Button variant="outline" onClick={onCancel} type="button">取消</Button>
        <Button
          onClick={() => onSave(form)}
          type="button"
          disabled={
            saving ||
            !form.name.trim() ||
            !form.apiKeyRef.name.trim() ||
            !form.defaultModel.trim() ||
            !form.baseUrl.trim() ||
            (!persisted && !form.apiKey.trim())
          }
        >
          {saving ? '保存中...' : '保存'}
        </Button>
      </div>
    </Card>
  );
}

export default function SettingsPage() {
  const [providers, setProviders] = useState<ModelProviderConfig[]>([]);
  const [editingProvider, setEditingProvider] = useState<ModelProviderConfig | null>(null);
  const [defaultGenerateProvider, setDefaultGenerateProvider] = useState('');
  const [defaultRepairProvider, setDefaultRepairProvider] = useState('');
  const [defaultValidateProvider, setDefaultValidateProvider] = useState('');
  const [blockOnMissingConfig, setBlockOnMissingConfig] = useState(true);
  const [testResults, setTestResults] = useState<Record<string, ConnectionTestResult>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const settingsLoaded = useRef(false);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const enabledProviders = useMemo(() => providers.filter((provider) => provider.enabled), [providers]);
  // 默认策略下拉只列出具备对应角色的 Provider，与后端按角色解析的逻辑保持一致。
  const generationProviders = useMemo(
    () => enabledProviders.filter((provider) => provider.roles.includes('generation')),
    [enabledProviders],
  );
  const repairProviders = useMemo(
    () => enabledProviders.filter((provider) => provider.roles.includes('repair')),
    [enabledProviders],
  );
  const validateProviders = useMemo(
    () => enabledProviders.filter((provider) =>
      provider.roles.includes('activation-evaluation')
      || provider.roles.includes('implementation-evaluation')
      || provider.roles.includes('validation-explanation')),
    [enabledProviders],
  );

  const loadProviders = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [loadedProviders, loadedSettings] = await Promise.all([
        listModelProviders(),
        getSettings().catch(() => null),
      ]);
      setProviders(loadedProviders);
      if (loadedSettings && !settingsLoaded.current) {
        settingsLoaded.current = true;
        setDefaultGenerateProvider(loadedSettings.defaultGenerateProvider);
        setDefaultRepairProvider(loadedSettings.defaultRepairProvider);
        setDefaultValidateProvider(loadedSettings.defaultValidateProvider);
        setBlockOnMissingConfig(loadedSettings.blockOnMissingConfig);
      }
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadProviders();
  }, [loadProviders]);

  // Clean up pending save timer on unmount
  useEffect(() => {
    return () => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    };
  }, []);

  // Debounced save of settings whenever they change
  const debouncedSaveSettings = useCallback((settings: AppSettings) => {
    if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
    saveTimerRef.current = setTimeout(() => {
      saveSettings(settings).catch((err) => {
        setError(messageFromError(err));
      });
    }, 500);
  }, []);

  useEffect(() => {
    if (!settingsLoaded.current) return;
    debouncedSaveSettings({
      defaultGenerateProvider,
      defaultRepairProvider,
      defaultValidateProvider,
      blockOnMissingConfig,
    });
  }, [defaultGenerateProvider, defaultRepairProvider, defaultValidateProvider, blockOnMissingConfig, debouncedSaveSettings]);

  // Auto-select first provider with the matching role if current selection is invalid
  useEffect(() => {
    if (!settingsLoaded.current) return;
    if (!generationProviders.some((provider) => provider.id === defaultGenerateProvider)) {
      setDefaultGenerateProvider(generationProviders[0]?.id ?? '');
    }
    if (!repairProviders.some((provider) => provider.id === defaultRepairProvider)) {
      setDefaultRepairProvider(repairProviders[0]?.id ?? '');
    }
    if (!validateProviders.some((provider) => provider.id === defaultValidateProvider)) {
      setDefaultValidateProvider(validateProviders[0]?.id ?? '');
    }
  }, [defaultGenerateProvider, defaultRepairProvider, defaultValidateProvider, generationProviders, repairProviders, validateProviders]);

  const persistedEditingProvider = Boolean(editingProvider && providers.some((provider) => provider.id === editingProvider.id));

  const handleAddProvider = () => {
    setEditingProvider(emptyProvider());
  };

  const handleSaveProvider = useCallback(async (provider: ProviderForm) => {
    setSaving(true);
    setError(null);
    try {
      const persisted = providers.some((item) => item.id === provider.id);
      const saved = persisted
        ? await updateModelProvider(provider.id, toPayload(provider))
        : await createModelProvider(toPayload(provider));

      setProviders((prev) => {
        if (persisted) {
          return prev.map((item) => (item.id === provider.id ? saved : item));
        }
        return [saved, ...prev];
      });
      setEditingProvider(null);
      window.dispatchEvent(new Event('skillforge-provider-changed'));
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setSaving(false);
    }
  }, [providers]);

  const handleDeleteProvider = useCallback(async (id: string) => {
    if (!window.confirm('确认删除此 Provider？此操作不可撤销。')) return;
    setError(null);
    try {
      await deleteModelProvider(id);
      setProviders((prev) => prev.filter((provider) => provider.id !== id));
      window.dispatchEvent(new Event('skillforge-provider-changed'));
    } catch (err) {
      setError(messageFromError(err));
    }
  }, []);

  const handleTestConnection = useCallback(async (id: string) => {
    if (!providers.some((provider) => provider.id === id)) {
      setTestResults((prev) => ({
        ...prev,
        [id]: { status: 'error', errorCategory: 'unknown', errorMessage: '请先保存 Provider，再测试连接。' },
      }));
      return;
    }

    setTestResults((prev) => ({ ...prev, [id]: { status: 'testing' } }));
    setError(null);
    try {
      const result = await testModelProvider(id);
      setTestResults((prev) => ({ ...prev, [id]: toConnectionResult(result) }));
      await loadProviders();
      window.dispatchEvent(new Event('skillforge-provider-changed'));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [id]: { status: 'error', errorCategory: 'unknown', errorMessage: messageFromError(err) },
      }));
    }
  }, [loadProviders, providers]);

  if (editingProvider) {
    return (
      <div className="flex flex-col flex-1">
        <PageHeader
          title="设置"
          sub={persistedEditingProvider ? '编辑 Provider' : '新增 Provider'}
        />

        {error && (
          <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        <ProviderEditor
          provider={editingProvider}
          persisted={persistedEditingProvider}
          onSave={handleSaveProvider}
          onCancel={() => setEditingProvider(null)}
          onTest={handleTestConnection}
          testResult={testResults[editingProvider.id] || { status: 'idle' }}
          saving={saving}
        />
      </div>
    );
  }

  return (
    <div className="flex flex-col flex-1">
      <PageHeader title="设置" sub="模型 Provider 与默认策略" />

      {error && (
        <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex flex-col gap-4 max-w-[780px]">
        <Card className="mb-6 bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
          <div className="flex justify-between items-center mb-3">
            <p className="mb-0 text-xs tracking-[0.18em] uppercase text-muted-foreground">模型 Provider</p>
            <Button variant="outline" size="sm" onClick={handleAddProvider} type="button">+ 新增</Button>
          </div>
          <p className="text-xs text-muted-foreground my-0 mb-4">配置 Anthropic 协议或 OpenAI-compatible 协议的大模型供应商</p>

          {loading && <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">正在从后端加载 Provider...</div>}
          {!loading && providers.length === 0 && (
            <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">还没有配置任何 Provider，点击「新增」添加</div>
          )}

          {providers.map((provider) => {
            const testResult = testResults[provider.id] || (provider.lastTest ? toConnectionResult(provider.lastTest) : { status: 'idle' });

            return (
              <div key={provider.id} className="mb-2 flex items-center justify-between gap-3 rounded-[var(--radius-md)] border border-panel-border bg-surface p-3 px-4 transition-[border-color,background-color] duration-200 hover:border-white/15 hover:bg-surface-up">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-sm font-semibold">{provider.name || '未命名'}</span>
                    <Badge className={cn(
                      'text-[11px] tracking-widest uppercase gap-1.5',
                      provider.enabled
                        ? 'bg-success-dim text-success border border-success-border'
                        : 'bg-white/5 text-muted-foreground border border-white/8'
                    )}>
                      <span className={cn('w-1.5 h-1.5 rounded-full', provider.enabled ? 'bg-success' : 'bg-muted-foreground')} />
                      {provider.enabled ? '启用' : '未启用'}
                    </Badge>
                  </div>
                  <div className="text-xs text-tertiary font-mono">
                    {provider.protocol === 'anthropic' ? 'Anthropic' : 'OpenAI-compat'} · {provider.defaultModel} · {provider.baseUrl}
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <Button variant="outline" size="sm" onClick={() => setEditingProvider(provider)} type="button">编辑</Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => void handleTestConnection(provider.id)}
                    type="button"
                    disabled={testResult.status === 'testing'}
                  >
                    测试
                  </Button>
                  <TestBadge result={testResult} />
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={() => void handleDeleteProvider(provider.id)}
                    type="button"
                  >
                    删除
                  </Button>
                </div>
              </div>
            );
          })}
        </Card>

        <Card className="mb-6 bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
          <p className="text-xs tracking-[0.18em] uppercase text-muted-foreground mb-2">默认策略</p>
          <p className="text-xs text-muted-foreground my-0 mb-4">为每个环节指定默认 Provider，实际调用会落实到该 Provider 配置的模型；未指定或不可用时回退到第一个具备对应角色的启用 Provider</p>
          <div className="flex flex-col gap-4">
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">生成 Provider / 模型</Label>
              <NativeSelect
                value={defaultGenerateProvider}
                onChange={(event) => setDefaultGenerateProvider(event.target.value)}
              >
                {generationProviders.map((provider) => (
                  <option key={provider.id} value={provider.id}>{`${provider.name || '未命名'} · ${provider.defaultModel}`}</option>
                ))}
                {generationProviders.length === 0 && <option value="">无具备 generation 角色的 Provider</option>}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">修复 Provider / 模型</Label>
              <NativeSelect
                value={defaultRepairProvider}
                onChange={(event) => setDefaultRepairProvider(event.target.value)}
              >
                {repairProviders.map((provider) => (
                  <option key={provider.id} value={provider.id}>{`${provider.name || '未命名'} · ${provider.defaultModel}`}</option>
                ))}
                {repairProviders.length === 0 && <option value="">无具备 repair 角色的 Provider</option>}
              </NativeSelect>
            </div>
            <div className="space-y-1.5">
              <Label className="text-muted-foreground">评测 Provider / 模型</Label>
              <NativeSelect
                value={defaultValidateProvider}
                onChange={(event) => setDefaultValidateProvider(event.target.value)}
              >
                {validateProviders.map((provider) => (
                  <option key={provider.id} value={provider.id}>{`${provider.name || '未命名'} · ${provider.defaultModel}`}</option>
                ))}
                {validateProviders.length === 0 && <option value="">无具备评测角色的 Provider</option>}
              </NativeSelect>
            </div>
            <Toggle label="配置缺失时阻止生成" checked={blockOnMissingConfig} onChange={setBlockOnMissingConfig} />
          </div>
        </Card>

        <Card className="bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
          <p className="text-xs tracking-[0.18em] uppercase text-muted-foreground mb-2">存储</p>
          <p className="text-xs text-muted-foreground my-0">草稿、Provider 和生成记录由本地后端持久化到 SQLite 与 artifact 目录</p>
        </Card>
      </div>
    </div>
  );
}
