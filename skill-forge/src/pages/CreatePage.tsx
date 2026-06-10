import { useCallback, useEffect, useRef, useState } from 'react';
import BasicStep from '../components/steps/BasicStep';
import PurposeStep from '../components/steps/PurposeStep';
import KnowledgeStep from '../components/steps/KnowledgeStep';
import SupplementStep from '../components/steps/SupplementStep';
import StepIndicator from '../components/StepIndicator';
import FileTree from '../components/FileTree';
import ValidationReport from '../components/ValidationReport';
import DownloadCard from '../components/DownloadCard';
import GenerationLoading from '../components/GenerationLoading';
import QualityScorePanel from '../components/QualityScorePanel';
import SupplementDialog from '../components/SupplementDialog';
import {
  createDraft,
  patchDraft,
  getGeneration,
  startGeneration,
  submitGenerationSupplement,
  toGenerationDownloadUrl,
} from '../api';
import { useDraft } from '../hooks/useDraft';
import { STEP_COMPLETION_WEIGHTS, STEP_KEYS, STEP_LABELS } from '../data';
import type {
  GenerationResult,
  ModelConnectionStatus,
  SupplementAnswer,
} from '../types';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

type Phase = 'form' | 'generating' | 'result';
type AutosaveStatus = 'idle' | 'saving' | 'saved' | 'error';

const TERMINAL_STATUSES = new Set(['succeeded', 'degraded', 'interrupted', 'failed']);

const STEP_DESCRIPTIONS: Record<number, string> = {
  0: '填写 Skill 名称并选择目标平台',
  1: '说明使用时机、目标结果、大致流程和完成标准',
  2: '提供专业信息、强制规则、常见错误和协同 Skill',
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
  const [formError, setFormError] = useState<string | null>(null);
  const [autosaveStatus, setAutosaveStatus] = useState<AutosaveStatus>('idle');
  const [lastSavedAt, setLastSavedAt] = useState<number | null>(null);
  const [autosavedDraftId, setAutosavedDraftId] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSubmittingSupplement, setIsSubmittingSupplement] = useState(false);
  const [pollingEnabled, setPollingEnabled] = useState(
    Boolean(resumeGenerationId),
  );
  const resumePending = useRef(false);

  useEffect(() => {
    if (resumeGenerationId && resumeGenerationId !== generationId) {
      setGenerationId(resumeGenerationId);
      setPhase('generating');
      setPollingEnabled(true);
    }
  }, [resumeGenerationId]);

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
      || draft.supplement.content.trim(),
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

  const handleGenerate = useCallback(async () => {
    if (connection.status !== 'connected') {
      setFormError('模型尚未连接。请先在设置中配置并测试生成与评测模型。');
      return;
    }

    setFormError(null);
    setPhase('generating');
    setGeneration(null);
    setGenerationError(null);
    setIsGenerating(true);

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

  const handleBackToForm = useCallback(() => {
    setPollingEnabled(false);
    setPhase('form');
    setGenerationError(null);
  }, []);

  const handleNewDraft = useCallback(() => {
    setPollingEnabled(false);
    resetDraft();
    setCurrentStep(0);
    setGeneration(null);
    setGenerationId(null);
    setGenerationError(null);
    setFormError(null);
    setPhase('form');
  }, [resetDraft]);

  if (phase === 'form') {
    const stepKey = STEP_KEYS[currentStep];

    return (
      <div className="flex flex-1 flex-col">
        <section className="mb-5">
          <p className="mb-2 text-[12px] uppercase tracking-[0.22em] text-muted-foreground">NovaFDE</p>
          <h1 className="text-3xl font-semibold leading-tight">创建新 Skill</h1>
        </section>

        <StepIndicator
          steps={steps}
          currentStep={currentStep}
          onStepClick={setCurrentStep}
          completions={completions}
        />

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

        <div className="grid min-h-[calc(100dvh-160px)] flex-1 grid-cols-1 items-stretch gap-3 lg:grid-cols-[1fr_var(--sidebar-width)]">
          <Card className="flex flex-col border-panel-border bg-panel p-5 shadow-md">
            <div className="mb-5">
              <h2 className="mb-1 text-lg font-semibold">{STEP_LABELS[stepKey]}</h2>
              <p className="text-xs leading-normal text-muted-foreground">{STEP_DESCRIPTIONS[currentStep]}</p>
            </div>

            <div className="flex flex-1 flex-col">
              {stepKey === 'basic' && <BasicStep draft={draft} onUpdate={updateDraft} />}
              {stepKey === 'purpose' && <PurposeStep draft={draft} onUpdatePurpose={updatePurpose} />}
              {stepKey === 'knowledge' && <KnowledgeStep draft={draft} onUpdateKnowledge={updateKnowledge} />}
              {stepKey === 'supplement' && (
                <SupplementStep
                  content={draft.supplement.content}
                  onChange={(content) => updateDraft({ supplement: { content } })}
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
              {currentStep < STEP_KEYS.length - 1 ? (
                <Button onClick={() => setCurrentStep((step) => step + 1)} type="button">
                  下一步
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

          <div className="top-7 flex flex-col gap-3 self-stretch lg:sticky">
            <Card className="border-panel-border bg-panel p-4 shadow-md">
              <p className="mb-2 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">信息完整度</p>
              <div className="mt-2 flex flex-col gap-2">
                {STEP_KEYS.map((key, index) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="min-w-[72px] text-xs text-muted-foreground">{STEP_LABELS[key]}</span>
                    <div className="h-[3px] flex-1 overflow-hidden rounded-full bg-white/6">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${completions[index]}%`,
                          background: completions[index] >= 80
                            ? 'var(--color-success)'
                            : 'var(--color-accent)',
                        }}
                      />
                    </div>
                    <span className="min-w-[28px] whitespace-nowrap text-right font-mono text-[12px] text-tertiary">
                      {completions[index]}%
                    </span>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="border-panel-border bg-panel p-4 shadow-md">
              <p className="mb-2 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">总完成度</p>
              <Progress value={overallCompletion} className="mt-2 h-1.5" />
              <p className="mt-2 text-center text-xl font-semibold">{overallCompletion}%</p>
            </Card>

            <Card className="border-panel-border bg-panel p-4 shadow-md">
              <p className="mb-2 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">生成策略</p>
              <p className="text-xs leading-snug text-muted-foreground">
                Agent 生成结构化 Skill IR，经过确定性校验、触发评测和实现评测后，最多定向优化三轮。
              </p>
            </Card>

            <Card className="border-panel-border bg-panel p-4 shadow-md">
              <p className="mb-2 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">自动保存</p>
              <p className={cn(
                'text-xs leading-snug',
                autosaveStatus === 'error'
                  ? 'text-warning'
                  : autosaveStatus === 'saved'
                    ? 'text-success'
                    : 'text-muted-foreground',
              )}>
                {autosaveStatus === 'idle' && '开始填写后会保存到本地 SQLite'}
                {autosaveStatus === 'saving' && '正在保存草稿...'}
                {autosaveStatus === 'saved' && `已保存 ${lastSavedAt ? new Date(lastSavedAt).toLocaleTimeString() : ''}`}
                {autosaveStatus === 'error' && '自动保存失败，请检查本地后端'}
              </p>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (phase === 'generating') {
    const report = generation?.qualityReport;
    const isAwaitingInput = generation?.status === 'awaiting_user_input';
    return (
      <>
        {!isAwaitingInput && (
          <GenerationLoading
            stage={generation?.currentStage ?? 'queued'}
            progress={generation?.progress ?? 0}
            currentRound={generation?.currentRound ?? 0}
            maxRepairRounds={generation?.maxRepairRounds ?? 3}
            isFailed={generation?.status === 'failed'}
          />
        )}
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
          <Alert className="fixed bottom-5 left-1/2 z-[60] w-[min(680px,calc(100%-2rem))] -translate-x-1/2 border-warning-border bg-panel text-warning shadow-2xl">
            <AlertDescription>{generationError}</AlertDescription>
          </Alert>
        )}
      </>
    );
  }

  if (!generation) {
    return (
      <div className="flex flex-1 flex-col">
        <h1 className="mb-5 text-3xl font-semibold">生成失败</h1>
        <Card className="max-w-[720px] border-panel-border bg-panel p-5 shadow-md">
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

  return (
    <div className="flex flex-1 flex-col">
      <section className="mb-5">
        <p className="mb-2 text-[12px] uppercase tracking-[0.22em] text-muted-foreground">NovaFDE</p>
        <h1 className="text-3xl font-semibold leading-tight">{title}</h1>
      </section>

      <div className="grid flex-1 grid-cols-1 items-start gap-3 lg:grid-cols-[1fr_var(--sidebar-width)]">
        <div className="flex flex-col gap-3">
          {generationError && (
            <Alert className="border-warning-border bg-warning-dim text-warning">
              <AlertDescription>{generationError}</AlertDescription>
            </Alert>
          )}

          <Card className="border-panel-border bg-panel p-5 shadow-md">
            <p className="mb-4 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">文件结构</p>
            {generation.files.length > 0
              ? <FileTree files={generation.files} />
              : <p className="py-8 text-center text-sm text-muted-foreground">暂无文件输出</p>}
          </Card>

          <Card className="border-panel-border bg-panel p-5 shadow-md">
            <p className="mb-4 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">SKILL.md 预览</p>
            <pre className="m-0 max-h-[440px] overflow-auto whitespace-pre-wrap rounded-[var(--radius-md)] border border-white/6 bg-[#020202] p-4 font-mono text-xs leading-[1.7] text-[#f5f5f5]">
              {generation.skillMd || '暂无预览'}
            </pre>
          </Card>

          <Card className="border-panel-border bg-panel p-5 shadow-md">
            <p className="mb-4 text-[12px] uppercase tracking-[0.18em] text-muted-foreground">确定性校验</p>
            {generation.validation.length > 0
              ? <ValidationReport items={generation.validation} />
              : <p className="py-8 text-center text-sm text-muted-foreground">暂无校验结果</p>}
          </Card>

          {generation.errorMessage && (
            <Alert className="border-warning-border bg-warning-dim text-warning">
              <AlertDescription>{generation.errorMessage}</AlertDescription>
            </Alert>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={handleBackToForm} type="button">返回编辑</Button>
            <Button variant="destructive" onClick={handleNewDraft} type="button">新建草稿</Button>
          </div>
        </div>

        <div className="top-7 flex flex-col gap-3 self-stretch lg:sticky">
          {generation.qualityReport && <QualityScorePanel report={generation.qualityReport} />}

          {downloadable && generation.downloadInfo && (
            <DownloadCard
              info={generation.downloadInfo}
              onDownload={() => window.location.assign(toGenerationDownloadUrl(generation.id))}
            />
          )}

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
      </div>
    </div>
  );
}
