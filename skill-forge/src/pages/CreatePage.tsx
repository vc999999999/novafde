import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import BasicStep from '../components/steps/BasicStep';
import PurposeStep from '../components/steps/PurposeStep';
import KnowledgeStep from '../components/steps/KnowledgeStep';
import SupplementStep from '../components/steps/SupplementStep';
import PageHeader from '../components/PageHeader';
import StepIndicator from '../components/StepIndicator';
import StepRail from '../components/StepRail';
import ValidationReport from '../components/ValidationReport';
import GenerationLoading from '../components/GenerationLoading';
import QualityScorePanel from '../components/QualityScorePanel';
import SupplementDialog from '../components/SupplementDialog';
import SkillSpecPanel from '../components/SkillSpecPanel';
import TriggerEvalSetManager from '../components/TriggerEvalSetManager';
import {
  ApiError,
  cancelGeneration,
  cancelTaskAb,
  cancelTriggerOptimization,
  createDraft,
  getTaskAb,
  getTriggerOptimization,
  patchDraft,
  getGeneration,
  getGenerationSpec,
  installGeneration,
  startGeneration,
  startTaskAb,
  startTriggerOptimization,
  submitGenerationSupplement,
  toGenerationDownloadUrl,
} from '../api';
import { useDraft } from '../hooks/useDraft';
import { STEP_COMPLETION_WEIGHTS, STEP_KEYS, STEP_LABELS } from '../data';
import type {
  GenerationResult,
  InstallResult,
  ModelConnectionStatus,
  SkillSpecResponse,
  SupplementAnswer,
  TriggerOptimizationCreateRequest,
  TriggerOptimizationRun,
  TaskABRun,
} from '../types';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { ArrowRight, CircleAlert, CircleCheck, CircleX, Download, FlaskConical, HardDriveDownload, Sparkles } from 'lucide-react';
import { cn } from '@/lib/utils';

type Phase = 'form' | 'generating' | 'result';
type AutosaveStatus = 'idle' | 'saving' | 'saved' | 'error';

const TERMINAL_STATUSES = new Set(['succeeded', 'degraded', 'interrupted', 'failed']);

const STEP_DESCRIPTIONS: Record<number, string> = {
  0: '填写 Skill 名称并选择目标平台',
  1: '只需说明使用时机和目标结果，其余由 Agent 自动补全',
  2: '本步全部可选：补充专业信息、强制规则、常见错误和协同 Skill 能提升生成质量',
  3: '自由补充背景或偏好，也可以直接留空',
};

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败，请检查本地后端是否正在运行。';
}

export default function CreatePage({
  connection,
  onOpenSettings,
  resumeGenerationId,
}: {
  connection: ModelConnectionStatus;
  onOpenSettings: () => void;
  resumeGenerationId: string | null;
}) {
  const { draft, updateDraft, updatePurpose, updateKnowledge, resetDraft } = useDraft();
  const [currentStep, setCurrentStep] = useState(0);
  const [phase, setPhase] = useState<Phase>(
    resumeGenerationId ? 'generating' : 'form',
  );
  const [generation, setGeneration] = useState<GenerationResult | null>(null);
  const [generationId, setGenerationId] = useState<string | null>(
    resumeGenerationId,
  );
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [skillSpec, setSkillSpec] = useState<SkillSpecResponse | null>(null);
  const [skillSpecError, setSkillSpecError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [autosaveStatus, setAutosaveStatus] = useState<AutosaveStatus>('idle');
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [autosavedDraftId, setAutosavedDraftId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isInstalling, setIsInstalling] = useState(false);
  const [installResult, setInstallResult] = useState<InstallResult | null>(null);
  const [installError, setInstallError] = useState<string | null>(null);
  const [isSubmittingSupplement, setIsSubmittingSupplement] = useState(false);
  const [pollingEnabled, setPollingEnabled] = useState(
    Boolean(resumeGenerationId),
  );
  const resumePending = useRef(false);
  const [prevResumeId, setPrevResumeId] = useState(resumeGenerationId);
  const generationSpecAvailable = generation?.skillSpecAvailable ?? false;
  const generationSpecRevision = generation?.skillSpecRevision ?? null;

  // --- Empirical closed loops state ---
  const [triggerPolling, setTriggerPolling] = useState(false);
  const [taskAbPolling, setTaskAbPolling] = useState(false);
  const [triggerCancelling, setTriggerCancelling] = useState(false);
  const [taskAbCancelling, setTaskAbCancelling] = useState(false);
  const [triggerRun, setTriggerRun] = useState<TriggerOptimizationRun | null>(null);
  const [triggerError, setTriggerError] = useState<string | null>(null);
  const [taskAbRun, setTaskAbRun] = useState<TaskABRun | null>(null);
  const [taskAbError, setTaskAbError] = useState<string | null>(null);
  const [selectedEvalSetId, setSelectedEvalSetId] = useState('auto');

  // Adjust state during render when the resume target changes (React-recommended
  // alternative to syncing props into state inside an effect).
  if (resumeGenerationId !== prevResumeId) {
    setPrevResumeId(resumeGenerationId);
    if (resumeGenerationId) {
      setGenerationId(resumeGenerationId);
      setPhase('generating');
      setPollingEnabled(true);
      setSkillSpec(null);
      setSkillSpecError(null);
    }
  }

  const steps = STEP_KEYS.map((key) => ({ key, label: STEP_LABELS[key] }));
  const completions = STEP_KEYS.map((key) => STEP_COMPLETION_WEIGHTS[key](draft));
  const overallCompletion = Math.round(
    completions.reduce((total, completion) => total + completion, 0) / completions.length,
  );

  useEffect(() => {
    const hasContent = Boolean(
      draft.displayName.trim()
      || draft.purpose.usage.trim()
      || draft.purpose.desiredOutcome.trim()
      || draft.purpose.process.length
      || draft.knowledge.professionalInformation.length
      || draft.knowledge.mandatoryRules.length
      || draft.knowledge.pitfalls.length
      || draft.supplement.content.trim()
      || draft.supplement.outputSpecFiles.length,
    );
    if (!hasContent) return;

    const timeout = window.setTimeout(() => {
      setAutosaveStatus('saving');
      if (autosavedDraftId) {
        patchDraft(autosavedDraftId, draft)
          .then(() => {
            setAutosaveStatus('saved');
            setLastSavedAt(Date.now());
          })
          .catch(() => setAutosaveStatus('error'));
      } else {
        createDraft(draft)
          .then((saved) => {
            setAutosavedDraftId(saved.id);
            setAutosaveStatus('saved');
            setLastSavedAt(Date.now());
          })
          .catch(() => setAutosaveStatus('error'));
      }
    }, 700);

    return () => window.clearTimeout(timeout);
  }, [draft, autosavedDraftId]);

  useEffect(() => {
    if (!generationId || !pollingEnabled) return;
    let cancelled = false;
    let timeout: number | undefined;

    const poll = async () => {
      try {
        const current = await getGeneration(generationId);
        if (cancelled) return;
        setGeneration(current);

        if (current.status === 'awaiting_user_input') {
          if (!resumePending.current) {
            // Continue polling at a slower rate to detect backend-side state changes
            timeout = window.setTimeout(poll, 5000);
            return;
          }
        } else {
          resumePending.current = false;
        }

        if (TERMINAL_STATUSES.has(current.status)) {
          setPollingEnabled(false);
          setPhase('result');
          return;
        }
        timeout = window.setTimeout(poll, 800);
      } catch (error) {
        if (cancelled) return;
        setGenerationError(messageFromError(error));
        setPollingEnabled(false);
        setPhase('result');
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timeout) window.clearTimeout(timeout);
    };
  }, [generationId, pollingEnabled]);

  // ---- Trigger optimization polling ----
  useEffect(() => {
    if (!triggerRun?.id || !triggerPolling) return;
    const isTerminal = triggerRun.status === 'completed'
      || triggerRun.status === 'failed'
      || triggerRun.status === 'interrupted';
    if (isTerminal) {
      setTriggerPolling(false);
      return;
    }

    let cancelled = false;
    let timeout: number | undefined;

    const poll = async () => {
      try {
        const current = await getTriggerOptimization(triggerRun.id);
        if (cancelled) return;
        setTriggerRun(current);
        if (current.status === 'completed'
          || current.status === 'failed'
          || current.status === 'interrupted') {
          setTriggerPolling(false);
          if (current.status === 'completed' && generationId) {
            getGeneration(generationId)
              .then(setGeneration)
              .catch((error) => setTriggerError(messageFromError(error)));
          }
          return;
        }
        timeout = window.setTimeout(poll, 2000);
      } catch (error) {
        if (cancelled) return;
        setTriggerError(messageFromError(error));
        setTriggerPolling(false);
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timeout) window.clearTimeout(timeout);
    };
  }, [triggerRun?.id, triggerPolling, generationId]);

  // ---- Task A/B polling ----
  useEffect(() => {
    if (!taskAbRun?.id || !taskAbPolling) return;
    const isTerminal = taskAbRun.status === 'completed'
      || taskAbRun.status === 'failed'
      || taskAbRun.status === 'interrupted';
    if (isTerminal) {
      setTaskAbPolling(false);
      return;
    }

    let cancelled = false;
    let timeout: number | undefined;

    const poll = async () => {
      try {
        const current = await getTaskAb(taskAbRun.id);
        if (cancelled) return;
        setTaskAbRun(current);
        if (current.status === 'completed'
          || current.status === 'failed'
          || current.status === 'interrupted') {
          setTaskAbPolling(false);
          return;
        }
        timeout = window.setTimeout(poll, 2000);
      } catch (error) {
        if (cancelled) return;
        setTaskAbError(messageFromError(error));
        setTaskAbPolling(false);
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timeout) window.clearTimeout(timeout);
    };
  }, [taskAbRun?.id, taskAbPolling]);

  useEffect(() => {
    if (!generationId || !generationSpecAvailable) return;
    if (skillSpec?.revision === generationSpecRevision) return;

    let cancelled = false;
    getGenerationSpec(generationId)
      .then((response) => {
        if (cancelled) return;
        setSkillSpec(response);
        setSkillSpecError(null);
      })
      .catch(() => {
        if (cancelled) return;
        setSkillSpecError('生成规格加载失败，请稍后刷新。');
      });
    return () => {
      cancelled = true;
    };
  }, [
    generationId,
    generationSpecAvailable,
    generationSpecRevision,
    skillSpec?.revision,
  ]);

  const handleGenerate = useCallback(async () => {
    if (connection.status !== 'connected') {
      setFormError('模型尚未连接。请先在设置中配置并测试生成与评测模型。');
      return;
    }

    setFormError(null);
    setPhase('generating');
    setGeneration(null);
    setSkillSpec(null);
    setSkillSpecError(null);
    setGenerationError(null);
    setIsGenerating(true);
    setIsCancelling(false);

    try {
      const savedDraft = await createDraft(draft);
      const started = await startGeneration(savedDraft.id);
      setGeneration(started);
      setGenerationId(started.id);
      setPollingEnabled(true);
    } catch (error) {
      setGenerationError(messageFromError(error));
      setPhase('result');
    } finally {
      setIsGenerating(false);
    }
  }, [connection.status, draft]);

  const submitSupplement = useCallback(async (answers: SupplementAnswer[], skip: boolean) => {
    if (!generationId) return;
    setIsSubmittingSupplement(true);
    setGenerationError(null);
    try {
      resumePending.current = true;
      const current = await submitGenerationSupplement(generationId, answers, skip);
      setGeneration(current);
      setPollingEnabled(true);
    } catch (error) {
      resumePending.current = false;
      setGenerationError(messageFromError(error));
    } finally {
      setIsSubmittingSupplement(false);
    }
  }, [generationId]);

  const handleCancelGeneration = useCallback(async () => {
    if (!generationId || isCancelling) return;
    setIsCancelling(true);
    setGenerationError(null);
    try {
      const current = await cancelGeneration(generationId);
      setGeneration(current);
      if (TERMINAL_STATUSES.has(current.status)) {
        setPollingEnabled(false);
        setPhase('result');
      } else {
        setPollingEnabled(true);
      }
    } catch (error) {
      setGenerationError(messageFromError(error));
    } finally {
      setIsCancelling(false);
    }
  }, [generationId, isCancelling]);

  const handleBackToForm = useCallback(() => {
    setPollingEnabled(false);
    setPhase('form');
    setGenerationError(null);
    setIsCancelling(false);
    setInstallResult(null);
    setInstallError(null);
  }, []);

  const handleNewDraft = useCallback(() => {
    setPollingEnabled(false);
    resetDraft();
    setCurrentStep(0);
    setGeneration(null);
    setGenerationId(null);
    setGenerationError(null);
    setSkillSpec(null);
    setSkillSpecError(null);
    setFormError(null);
    setInstallResult(null);
    setInstallError(null);
    setPhase('form');
  }, [resetDraft]);

  const handleInstall = useCallback(async () => {
    if (!generation || isInstalling) return;
    setIsInstalling(true);
    setInstallError(null);
    setInstallResult(null);
    try {
      try {
        setInstallResult(await installGeneration(generation.id));
      } catch (error) {
        const detail = error instanceof ApiError && error.status === 409
          ? (error.detail as { detail?: { code?: string; path?: string } } | null)?.detail
          : undefined;
        if (detail?.code !== 'INSTALL_TARGET_EXISTS') throw error;
        const confirmed = window.confirm(
          `目标目录已存在同名 Skill：\n${detail.path}\n\n确认覆盖安装吗？`,
        );
        if (!confirmed) return;
        setInstallResult(await installGeneration(generation.id, { overwrite: true }));
      }
    } catch (error) {
      setInstallError(messageFromError(error));
    } finally {
      setIsInstalling(false);
    }
  }, [generation, isInstalling]);

  // ---- Trigger optimization handlers ----
  const handleStartTriggerOptimization = useCallback(async () => {
    if (!generation || !generation.id || triggerPolling) return;
    setTriggerError(null);
    setTriggerRun(null);
    setTriggerPolling(true);
    try {
      const saved = await startTriggerOptimization(generation.id, {
        evalSetId: selectedEvalSetId,
        maxIterations: 5,
        runsPerQuery: 2,
        triggerThreshold: 0.8,
      } as TriggerOptimizationCreateRequest);
      setTriggerRun(saved);
    } catch (error) {
      setTriggerError(messageFromError(error));
      setTriggerPolling(false);
    }
  }, [generation, triggerPolling, selectedEvalSetId]);

  const handleCancelTriggerOptimization = useCallback(async () => {
    if (!triggerRun?.id || triggerCancelling) return;
    setTriggerCancelling(true);
    try {
      const current = await cancelTriggerOptimization(triggerRun.id);
      setTriggerRun(current);
    } catch (error) {
      setTriggerError(messageFromError(error));
    } finally {
      setTriggerCancelling(false);
    }
  }, [triggerRun, triggerCancelling]);

  // ---- Task A/B handlers ----
  const handleStartTaskAb = useCallback(async () => {
    if (!generation || !generation.id || taskAbPolling) return;
    setTaskAbError(null);
    setTaskAbRun(null);
    setTaskAbPolling(true);
    try {
      const prompts = [
        draft.purpose.usage.trim(),
        draft.purpose.desiredOutcome.trim(),
      ].filter(Boolean);
      if (prompts.length === 0) {
        setTaskAbError('请先在表单中填写技能用途和目标结果。');
        setTaskAbPolling(false);
        return;
      }
      const run = await startTaskAb(generation.id, {
        prompts,
        runsPerPrompt: 2,
      });
      setTaskAbRun(run);
    } catch (error) {
      setTaskAbError(messageFromError(error));
      setTaskAbPolling(false);
    }
  }, [generation, taskAbPolling, draft.purpose.usage, draft.purpose.desiredOutcome]);

  const handleCancelTaskAb = useCallback(async () => {
    if (!taskAbRun?.id || taskAbCancelling) return;
    setTaskAbCancelling(true);
    try {
      const current = await cancelTaskAb(taskAbRun.id);
      setTaskAbRun(current);
    } catch (error) {
      setTaskAbError(messageFromError(error));
    } finally {
      setTaskAbCancelling(false);
    }
  }, [taskAbRun, taskAbCancelling]);

  if (phase === 'form') {
    const stepKey = STEP_KEYS[currentStep];
    const nextStepKey = currentStep < STEP_KEYS.length - 1 ? STEP_KEYS[currentStep + 1] : null;

    return (
      <div className="flex flex-1 flex-col">
        <PageHeader
          title="创建新 Skill"
          sub={(
            <>
              <span data-numeric className="font-mono text-xs text-tertiary">
                {String(currentStep + 1).padStart(2, '0')} · {String(STEP_KEYS.length).padStart(2, '0')}
              </span>
              <span className="truncate">{STEP_LABELS[stepKey]}</span>
            </>
          )}
          actions={(
            <div className="flex items-center gap-2">
            <span
              aria-hidden
              className={cn(
                'size-1.5 rounded-full transition-colors duration-300',
                autosaveStatus === 'error'
                  ? 'bg-warning'
                  : autosaveStatus === 'saved'
                    ? 'bg-success'
                    : autosaveStatus === 'saving'
                      ? 'bg-accent animate-[saving-pulse_1s_ease-in-out_infinite]'
                      : 'bg-black/20',
              )}
            />
            <span className={cn(
              'text-xs transition-colors duration-300',
              autosaveStatus === 'error'
                ? 'text-warning'
                : autosaveStatus === 'saved'
                  ? 'text-success'
                  : 'text-tertiary',
            )}>
              {autosaveStatus === 'idle' && '自动保存到本地'}
              {autosaveStatus === 'saving' && '正在保存草稿...'}
              {autosaveStatus === 'saved' && `已保存 ${lastSavedAt ? new Date(lastSavedAt).toLocaleTimeString() : ''}`}
              {autosaveStatus === 'error' && '自动保存失败'}
            </span>
            </div>
          )}
        />

        <div className="lg:hidden">
          <StepIndicator
            steps={steps}
            currentStep={currentStep}
            onStepClick={setCurrentStep}
            completions={completions}
          />
        </div>

        {formError && (
          <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
            <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
              <span>{formError}</span>
              <Button type="button" size="sm" variant="outline" onClick={onOpenSettings}>
                打开设置
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-[230px_minmax(0,1fr)]">
          <StepRail
            steps={steps}
            completions={completions}
            overall={overallCompletion}
            currentStep={currentStep}
            onStepClick={setCurrentStep}
            className="top-[84px] hidden self-start lg:sticky lg:flex"
          />

          <Card className="flex flex-col border-panel-border bg-panel p-6 shadow-md lg:min-h-[560px]">
            <div className="mb-6">
              <h2 className="mb-1 text-lg font-semibold">{STEP_LABELS[stepKey]}</h2>
              <p className="text-xs leading-normal text-muted-foreground">{STEP_DESCRIPTIONS[currentStep]}</p>
            </div>

            <div key={stepKey} className="animate-step-in flex w-full max-w-[600px] flex-col">
              {stepKey === 'basic' && <BasicStep draft={draft} onUpdate={updateDraft} />}
              {stepKey === 'purpose' && <PurposeStep draft={draft} onUpdatePurpose={updatePurpose} />}
              {stepKey === 'knowledge' && <KnowledgeStep draft={draft} onUpdateKnowledge={updateKnowledge} />}
              {stepKey === 'supplement' && (
                <SupplementStep
                  supplement={draft.supplement}
                  onUpdate={(supplement) => updateDraft({ supplement })}
                />
              )}
            </div>

            <div className="mt-auto flex items-center justify-between border-t border-panel-border pt-4">
              <Button
                variant="outline"
                onClick={() => setCurrentStep((step) => Math.max(0, step - 1))}
                disabled={currentStep === 0}
                type="button"
                className={cn(currentStep === 0 && 'opacity-30')}
              >
                上一步
              </Button>
              {nextStepKey ? (
                <Button onClick={() => setCurrentStep((step) => step + 1)} type="button">
                  下一步：{STEP_LABELS[nextStepKey]}
                  <ArrowRight className="size-4" />
                </Button>
              ) : (
                <Button
                  onClick={handleGenerate}
                  type="button"
                  disabled={isGenerating || connection.status !== 'connected'}
                >
                  {isGenerating
                    ? '正在创建任务...'
                    : connection.status === 'connected'
                      ? '确认并生成'
                      : '请先连接模型'}
                </Button>
              )}
            </div>
          </Card>
        </div>
      </div>
    );
  }

  if (phase === 'generating') {
    const report = generation?.qualityReport;
    const isAwaitingInput = generation?.status === 'awaiting_user_input';
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader
          title="正在生成 Skill"
          sub={generation?.stageMessage || '质量优先模式会持续检查并修复输出'}
        />
        <div className={cn(
          'mx-auto grid w-full max-w-[1180px] items-stretch gap-5',
          (skillSpec || skillSpecError) && 'lg:grid-cols-[minmax(0,1fr)_340px]',
        )}>
          {!isAwaitingInput && (
            <GenerationLoading
              stage={generation?.currentStage ?? 'queued'}
              progress={generation?.progress ?? 0}
              currentRound={generation?.currentRound ?? 0}
              maxRepairRounds={generation?.maxRepairRounds ?? 3}
              stageAttempt={generation?.stageAttempt ?? 0}
              stageMaxAttempts={generation?.stageMaxAttempts ?? 3}
              completedStages={generation?.completedStages ?? []}
              stageMessage={generation?.stageMessage ?? ''}
              cancelRequested={generation?.cancelRequested ?? false}
              isCancelling={isCancelling}
              onCancel={() => void handleCancelGeneration()}
              isFailed={generation?.status === 'failed'}
            />
          )}
          {(skillSpec || skillSpecError) && (
            isAwaitingInput ? (
              <SkillSpecPanel
                response={skillSpec}
                error={skillSpecError}
                compact
                defaultOpen
                className="w-full"
              />
            ) : (
              /* 与左侧生成进度卡等高对齐，规格内容在卡片内部滚动 */
              <div className="relative">
                <SkillSpecPanel
                  response={skillSpec}
                  error={skillSpecError}
                  compact
                  defaultOpen
                  className="w-full lg:absolute lg:inset-0 lg:overflow-auto"
                />
              </div>
            )
          )}
        </div>
        {isAwaitingInput && generation.userQuestions.length > 0 && (
          <SupplementDialog
            key={generation.userQuestions.map((question) => question.issueId).join(':')}
            questions={generation.userQuestions}
            scores={{
              overall: report?.overallScore ?? null,
              activation: report?.activationScore ?? null,
              implementation: report?.implementationScore ?? null,
            }}
            submitting={isSubmittingSupplement}
            onSubmit={(answers) => void submitSupplement(answers, false)}
            onSkip={() => void submitSupplement([], true)}
          />
        )}
        {generationError && (
          <Alert className="mx-auto mt-4 w-full max-w-[680px] border-warning-border bg-panel text-warning shadow-md">
            <AlertDescription>{generationError}</AlertDescription>
          </Alert>
        )}
      </div>
    );
  }

  if (!generation) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="创建新 Skill" sub="生成失败" />
        <Card className="animate-step-in max-w-[720px] border-panel-border bg-panel p-5 shadow-md">
          <Alert className="border-warning-border bg-warning-dim text-warning">
            <AlertDescription>{generationError ?? '生成任务没有返回结果。'}</AlertDescription>
          </Alert>
          <Button className="mt-4" variant="outline" onClick={handleBackToForm} type="button">
            返回编辑
          </Button>
        </Card>
      </div>
    );
  }

  const downloadable = generation.status === 'succeeded' || generation.status === 'degraded';
  const title = generation.status === 'succeeded'
    ? '高质量 Skill 已生成'
    : generation.status === 'degraded'
      ? '已生成低分版本'
      : generation.status === 'interrupted'
        ? '任务已中断'
        : '生成失败';

  const StatusIcon = generation.status === 'succeeded'
    ? CircleCheck
    : generation.status === 'failed'
      ? CircleX
      : CircleAlert;
  const statusTone = generation.status === 'succeeded'
    ? 'border-success-border bg-success-dim text-success'
    : generation.status === 'failed'
      ? 'border-error-border bg-error-dim text-error'
      : 'border-warning-border bg-warning-dim text-warning';
  const downloadInfo = generation.downloadInfo;
  const hasArtifacts = Boolean(generation.skillMd)
    || generation.validation.length > 0;
  const resultTabDefault = generation.skillMd ? 'skillmd' : 'validation';

  return (
    <div className="flex flex-1 flex-col">
      <PageHeader title="创建新 Skill" sub="生成结果" />

      <Card className="animate-step-in mb-3 flex flex-row flex-wrap items-center justify-between gap-x-6 gap-y-4 border-panel-border bg-panel p-5 shadow-md">
        <div className="flex min-w-0 items-center gap-4">
          <div className={cn('flex size-11 shrink-0 items-center justify-center rounded-full border', statusTone)}>
            <StatusIcon className="size-5" />
          </div>
          <div className="min-w-0">
            <h2 className="text-xl font-semibold leading-tight">{title}</h2>
            {downloadable && downloadInfo ? (
              <p className="mt-1 truncate font-mono text-xs text-muted-foreground" data-numeric>
                {downloadInfo.packageName} · v{downloadInfo.version} · {downloadInfo.fileCount} 文件 · {downloadInfo.size}
              </p>
            ) : (
              <p className="mt-1 text-xs text-muted-foreground">
                {generation.status === 'interrupted' ? '任务在完成前被中断' : '可返回编辑后重新生成'}
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          {generation.qualityReport?.overallScore != null && (
            <div className="flex flex-col items-center">
              <span data-numeric className="font-mono text-2xl font-semibold leading-none">
                {Math.round(generation.qualityReport.overallScore)}
              </span>
              <span className="mt-1 text-[10px] tracking-[0.16em] text-tertiary">总分</span>
            </div>
          )}
          <div className="flex flex-wrap items-center gap-2">
            {downloadable && (
              <Button
                type="button"
                onClick={() => void handleInstall()}
                disabled={isInstalling}
              >
                <HardDriveDownload className="size-4" />
                {isInstalling ? '安装中…' : '安装到本地'}
              </Button>
            )}
            {downloadable && downloadInfo && (
              <Button
                type="button"
                variant="outline"
                onClick={() => window.location.assign(toGenerationDownloadUrl(generation.id))}
              >
                <Download className="size-4" />
                下载 zip
              </Button>
            )}
            <Button variant="outline" onClick={handleBackToForm} type="button">返回编辑</Button>
            <Button variant="destructive" onClick={handleNewDraft} type="button">新建草稿</Button>
            {downloadable && (
              <>
                <Button
                  variant="secondary"
                  type="button"
                  onClick={handleStartTriggerOptimization}
                  disabled={triggerPolling}
                >
                  <Sparkles className="size-4" />
                  {triggerPolling ? '优化中…' : '优化触发描述'}
                </Button>
                <Button
                  variant="outline"
                  type="button"
                  onClick={handleStartTaskAb}
                  disabled={taskAbPolling}
                >
                  <FlaskConical className="size-4" />
                  {taskAbPolling ? '评测中…' : '基线对照评测'}
                </Button>
              </>
            )}
          </div>
        </div>
      </Card>

      {installResult && (
        <Alert className="animate-step-in mb-3 border-success-border bg-success-dim text-success">
          <AlertDescription>
            已安装到 <span className="font-mono">{installResult.installedPath}</span>
            （{installResult.fileCount} 个文件{installResult.overwrote ? '，已覆盖原有版本' : ''}）。
            重启或刷新对应平台后即可使用。
          </AlertDescription>
        </Alert>
      )}
      {installError && (
        <Alert className="animate-step-in mb-3 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>安装失败：{installError}</AlertDescription>
        </Alert>
      )}

      {generationError && (
        <Alert className="animate-step-in mb-3 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{generationError}</AlertDescription>
        </Alert>
      )}
      {generation.errorMessage && (
        <Alert className="animate-step-in mb-3 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{generation.errorMessage}</AlertDescription>
        </Alert>
      )}

      {/* 实证闭环：评测集 + 触发优化 / 基线对照 */}
      {downloadable && generation?.id && (
        <Card className="animate-step-in mb-3 border-panel-border bg-panel p-5 shadow-md">
          <TriggerEvalSetManager
            selectedId={selectedEvalSetId}
            generationId={generation.id}
            onSelectId={setSelectedEvalSetId}
          />
        </Card>
      )}

      {/* 重要信息优先：质量评分 / 生成统计 / 生成规格在前，文件产物在后 */}
      <div className="grid flex-1 grid-cols-1 items-start gap-3 lg:grid-cols-[var(--sidebar-width)_minmax(0,1fr)]">
        <div
          className="animate-step-in top-[72px] flex flex-col gap-3 lg:sticky"
          style={{ '--enter-delay': '60ms' } as CSSProperties}
        >
          {generation.qualityReport && <QualityScorePanel report={generation.qualityReport} />}

          <Card className="border-panel-border bg-panel p-4 shadow-md">
            <p className="mb-2 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">生成统计</p>
            <div className="mt-2 flex flex-col gap-2">
              <div className="flex justify-between py-1 text-xs">
                <span className="text-muted-foreground">最终候选</span>
                <span>第 {generation.finalRound ?? generation.currentRound} 轮</span>
              </div>
              {generation.supplementScoreDelta !== null && (
                <div className="flex justify-between py-1 text-xs">
                  <span className="text-muted-foreground">补充后分数变化</span>
                  <span className={generation.supplementScoreDelta >= 0 ? 'text-success' : 'text-warning'}>
                    {generation.supplementScoreDelta >= 0 ? '+' : ''}{generation.supplementScoreDelta}
                  </span>
                </div>
              )}
              <div className="flex justify-between py-1 text-xs">
                <span className="text-muted-foreground">警告</span>
                <span className="text-warning">{generation.warnings} 项</span>
              </div>
              <div className="flex justify-between py-1 text-xs">
                <span className="text-muted-foreground">阻塞</span>
                <span className="text-error">{generation.blockingIssues} 项</span>
              </div>
              <div className="flex justify-between py-1 text-xs">
                <span className="text-muted-foreground">文件数</span>
                <span>{generation.downloadInfo?.fileCount || generation.files.length}</span>
              </div>
            </div>
          </Card>
        </div>

        <div
          className="animate-step-in flex flex-col gap-3"
          style={{ '--enter-delay': '120ms' } as CSSProperties}
        >
          {/* 生成规格面板 */}
          {(skillSpec || skillSpecError) && (
            <SkillSpecPanel
              response={skillSpec}
              error={skillSpecError}
            />
          )}

          {hasArtifacts ? (
            <Card className="border-panel-border bg-panel p-5 shadow-md">
              <Tabs defaultValue={resultTabDefault}>
                <TabsList className="mb-4 h-auto gap-1 rounded-full border border-panel-border bg-surface px-[3px] py-[3px]">
                  {[
                    { value: 'skillmd', label: 'SKILL.md 预览' },
                    { value: 'validation', label: '确定性校验' },
                  ].map((tab) => (
                    <TabsTrigger
                      key={tab.value}
                      value={tab.value}
                      className="flex-none rounded-full px-3.5 py-1.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground data-[state=active]:bg-black/12 data-[state=active]:text-foreground"
                    >
                      {tab.label}
                    </TabsTrigger>
                  ))}
                </TabsList>
                <TabsContent value="skillmd" className="animate-step-in">
                  <pre className="m-0 max-h-[520px] overflow-auto whitespace-pre-wrap rounded-[var(--radius-md)] border border-black/6 bg-[#060608] p-4 font-mono text-xs leading-[1.7] text-[#f5f5f5]">
                    {generation.skillMd || '暂无预览'}
                  </pre>
                </TabsContent>
                <TabsContent value="validation" className="animate-step-in">
                  {generation.validation.length > 0
                    ? <ValidationReport items={generation.validation} />
                    : <p className="py-8 text-center text-sm text-muted-foreground">暂无校验结果</p>}
                </TabsContent>
              </Tabs>
              </Card>
              ) : (
                !(skillSpec || skillSpecError) && (
                  <Card className="border-panel-border bg-panel p-5 shadow-md">
                    <p className="py-8 text-center text-sm text-muted-foreground">
                      本次任务没有产出可预览的内容
                    </p>
                  </Card>
                )
              )}

              {/* Trigger optimization panel */}
              {(triggerRun || triggerError) && (
                <Card className="animate-step-in border-panel-border bg-panel p-5 shadow-md">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-[12px] uppercase tracking-[0.18em] text-muted-foreground">
                      触发描述优化
                    </p>
                    <div className="flex items-center gap-2">
                      {triggerRun?.detectionPath && (
                        <span className="rounded-full border border-black/10 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                          {triggerRun.detectionPath === 'cli' ? 'CLI 真测' : 'Judge 代理'}
                        </span>
                      )}
                      {triggerRun?.provenance?.claudeBinaryPresent === false && (
                        <span className="rounded-full border border-warning-border px-2 py-0.5 text-[10px] text-warning">
                          CLI 不可用，已降级
                        </span>
                      )}
                      {triggerRun && !triggerPolling && triggerRun.status === 'completed' && (
                        <span className="rounded-full border border-success-border bg-success-dim px-2 py-0.5 text-[10px] text-success">
                          已完成
                        </span>
                      )}
                      {triggerRun && triggerPolling && (
                        <span className="rounded-full border border-accent-border bg-accent-dim px-2 py-0.5 text-[10px] animate-[saving-pulse_1s_ease-in-out_infinite]">
                          进行中…
                        </span>
                      )}
                    </div>
                  </div>

                  {triggerError && (
                    <Alert className="mb-3 border-warning-border bg-warning-dim text-warning">
                      <AlertDescription>{triggerError}</AlertDescription>
                    </Alert>
                  )}

                  {triggerRun && (
                    <>
                      {triggerRun.status === 'completed' && triggerRun.chosenDescription && (
                        <div className="mb-3">
                          <p className="mb-1 text-xs text-muted-foreground">优化后的描述</p>
                          <pre className="whitespace-pre-wrap rounded-[var(--radius-sm)] border border-black/6 bg-[#060608] p-3 font-mono text-xs leading-[1.7] text-[#f5f5f5]">
                            {triggerRun.chosenDescription}
                          </pre>
                        </div>
                      )}

                      {triggerRun.originalDescription !== triggerRun.chosenDescription && (
                        <div className="mb-3">
                          <p className="mb-1 text-xs text-muted-foreground">原始描述</p>
                          <pre className="whitespace-pre-wrap rounded-[var(--radius-sm)] border border-black/6 bg-[#060608] p-3 font-mono text-xs leading-[1.7] text-[#e0e0e0] line-through opacity-70">
                            {triggerRun.originalDescription}
                          </pre>
                        </div>
                      )}

                      <div className="mb-3 grid grid-cols-3 gap-3 text-center">
                        <div>
                          <span className="font-mono text-lg font-semibold">
                            {triggerRun.trainScore}
                          </span>
                          <p className="text-[10px] tracking-[0.16em] text-tertiary">训练集</p>
                        </div>
                        <div>
                          <span className="font-mono text-lg font-semibold">
                            {triggerRun.testScore ?? '—'}
                          </span>
                          <p className="text-[10px] tracking-[0.16em] text-tertiary">留出集</p>
                        </div>
                        <div>
                          <span className="font-mono text-lg font-semibold">
                            {triggerRun.iterations.length}
                          </span>
                          <p className="text-[10px] tracking-[0.16em] text-tertiary">迭代轮数</p>
                        </div>
                      </div>

                      {triggerRun.iterations.length > 0 && (
                        <div className="flex flex-col gap-2">
                          <p className="text-xs text-muted-foreground">逐轮改进</p>
                          {triggerRun.iterations.map((iter) => (
                            <div
                              key={iter.index}
                              className="flex items-center justify-between rounded-[var(--radius-sm)] border border-black/6 bg-surface px-3 py-2 text-xs"
                            >
                              <span className="text-muted-foreground">第 {iter.index + 1} 轮</span>
                              <span
                                className={cn(
                                  'font-mono',
                                  iter.trainPassed >= iter.trainTotal
                                    ? 'text-success'
                                    : 'text-warning',
                                )}
                              >
                                {iter.trainPassed}/{iter.trainTotal} 训练
                              </span>
                              <span className="text-muted-foreground">
                                {iter.testPassed != null ? `${iter.testPassed}/${iter.testTotal} 验证` : '—'}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}

                      {triggerRun.status === 'completed' && triggerRun.writebackFailed && (
                        <Alert className="mt-3 border-warning-border bg-warning-dim text-warning">
                          <AlertDescription>
                            优化已完成，但写回最终包失败：{triggerRun.writebackError || triggerRun.errorMessage}
                          </AlertDescription>
                        </Alert>
                      )}

                      {triggerRun.status === 'completed' && !triggerPolling && !triggerRun.writebackFailed
                        && triggerRun.chosenDescription !== triggerRun.originalDescription && (
                        <div className="mt-3">
                          <Button
                            variant="outline"
                            size="sm"
                            type="button"
                            onClick={() => window.location.assign(toGenerationDownloadUrl(triggerRun.generationId))}
                          >
                            <Download className="size-3.5" />
                            下载更新后的 Skill
                          </Button>
                        </div>
                      )}

                      {(triggerRun.status === 'queued'
                        || triggerRun.status === 'measuring'
                        || triggerRun.status === 'rewriting') && (
                        <div className="mt-3">
                          <Button
                            variant="ghost"
                            size="sm"
                            type="button"
                            disabled={triggerCancelling}
                            onClick={handleCancelTriggerOptimization}
                          >
                            {triggerCancelling ? '取消中…' : '取消优化'}
                          </Button>
                        </div>
                      )}
                    </>
                  )}

                  {triggerRun?.status === 'failed' && triggerRun.errorMessage && (
                    <Alert className="mt-3 border-warning-border bg-warning-dim text-warning">
                      <AlertDescription>{triggerRun.errorMessage}</AlertDescription>
                    </Alert>
                  )}
                </Card>
              )}

              {/* Task A/B panel */}
              {(taskAbRun || taskAbError) && (
                <Card className="animate-step-in border-panel-border bg-panel p-5 shadow-md">
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-[12px] uppercase tracking-[0.18em] text-muted-foreground">
                      基线对照评测
                    </p>
                    <div className="flex items-center gap-2">
                      {taskAbRun?.detectionPath && (
                        <span className="rounded-full border border-black/10 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                          执行：{taskAbRun.detectionPath === 'cli' ? 'CLI 真跑' : 'LLM 代理'}
                        </span>
                      )}
                      <span className="rounded-full border border-black/10 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                        评分：Judge
                      </span>
                      {taskAbRun && !taskAbPolling && taskAbRun.status === 'completed' && (
                        <span className="rounded-full border border-success-border bg-success-dim px-2 py-0.5 text-[10px] text-success">
                          已完成
                        </span>
                      )}
                      {taskAbRun && taskAbPolling && (
                        <span className="rounded-full border border-accent-border bg-accent-dim px-2 py-0.5 text-[10px] animate-[saving-pulse_1s_ease-in-out_infinite]">
                          评测中…
                        </span>
                      )}
                    </div>
                  </div>

                  {taskAbError && (
                    <Alert className="mb-3 border-warning-border bg-warning-dim text-warning">
                      <AlertDescription>{taskAbError}</AlertDescription>
                    </Alert>
                  )}

                  {taskAbRun && taskAbRun.verdicts.length > 0 && (
                    <div className="mb-3 flex flex-col gap-2">
                      {taskAbRun.verdicts.map((v, idx) => (
                        <div
                          key={idx}
                          className="flex items-start gap-3 rounded-[var(--radius-sm)] border border-black/6 bg-surface px-3 py-2 text-xs"
                        >
                          <span
                            className={cn(
                              'mt-0.5 shrink-0 rounded-full border px-1.5 py-0.5 font-mono text-[10px]',
                              v.betterConfig === 'with_skill' && 'border-success-border bg-success-dim text-success',
                              v.betterConfig === 'baseline' && 'border-warning-border bg-warning-dim text-warning',
                              v.betterConfig === 'tie' && 'border-black/10 bg-black/5 text-muted-foreground',
                            )}
                          >
                            {v.betterConfig === 'with_skill' ? 'Skill 胜' : v.betterConfig === 'baseline' ? '基线胜' : '平局'}
                          </span>
                          <div className="min-w-0">
                            <p className="mb-0.5 truncate text-muted-foreground">
                              {typeof v.prompt === 'string' ? v.prompt : JSON.stringify(v.prompt)}
                            </p>
                            <p className="line-clamp-2 text-[11px] text-muted-foreground">
                              {v.reasoning}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {(taskAbRun && (taskAbRun.status === 'queued'
                    || taskAbRun.status === 'running_with_skill'
                    || taskAbRun.status === 'running_baseline'
                    || taskAbRun.status === 'grading')) && (
                    <div className="mt-3">
                      <Button
                        variant="ghost"
                        size="sm"
                        type="button"
                        disabled={taskAbCancelling}
                        onClick={handleCancelTaskAb}
                      >
                        {taskAbCancelling ? '取消中…' : '取消评测'}
                      </Button>
                    </div>
                  )}

                  {taskAbRun?.status === 'completed' && !taskAbPolling && (
                    <div className="mt-3">
                      <Button
                        variant="outline"
                        size="sm"
                        type="button"
                        onClick={() => window.location.assign(toGenerationDownloadUrl(taskAbRun.generationId))}
                      >
                        <Download className="size-3.5" />
                        查看对应的 Skill
                      </Button>
                    </div>
                  )}
                </Card>
              )}
        </div>
      </div>
    </div>
  );
}
