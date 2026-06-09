import { useState, useCallback } from 'react';
import StepIndicator from '../components/StepIndicator';
import BasicStep from '../components/steps/BasicStep';
import TriggerStep from '../components/steps/TriggerStep';
import WorkflowStep from '../components/steps/WorkflowStep';
import ContextStep from '../components/steps/ContextStep';
import KnowledgeStep from '../components/steps/KnowledgeStep';
import OutputStep from '../components/steps/OutputStep';
import SupplementStep from '../components/steps/SupplementStep';
import PipelineProgress from '../components/PipelineProgress';
import FileTree from '../components/FileTree';
import ValidationReport from '../components/ValidationReport';
import DownloadCard from '../components/DownloadCard';
import { createDraft, generateDraft, toGenerationDownloadUrl } from '../api';
import { useDraft } from '../hooks/useDraft';
import {
  STEP_KEYS,
  STEP_LABELS,
  STEP_COMPLETION_WEIGHTS,
} from '../data';
import type { ChatMessage, GenerationResult, GenerationStage } from '../types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

type Phase = 'form' | 'generating' | 'result';

const STEP_DESCRIPTIONS: Record<number, string> = {
  0: '填写 Skill 的基本信息',
  1: '定义 Skill 的触发条件',
  2: '设计工作流步骤',
  3: '定义文件系统上下文',
  4: '添加 Agent 不知道的经验和易错点',
  5: '控制生成输出',
  6: '通过聊天补充信息',
};

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : '请求失败，请检查后端服务是否正在运行。';
}

export default function CreatePage() {
  const { draft, updateDraft, updateTrigger, updateWorkflow, updateContext, updateKnowledge, updateOutputControl, resetDraft } = useDraft();
  const [currentStep, setCurrentStep] = useState(0);
  const [phase, setPhase] = useState<Phase>('form');
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [genProgress, setGenProgress] = useState(0);
  const [genStage, setGenStage] = useState<GenerationStage | null>(null);
  const [generation, setGeneration] = useState<GenerationResult | null>(null);
  const [generationError, setGenerationError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);

  const steps = STEP_KEYS.map((key) => ({ key, label: STEP_LABELS[key] }));
  const completions = STEP_KEYS.map((key) => STEP_COMPLETION_WEIGHTS[key](draft));
  const overallCompletion = Math.round(completions.reduce((a, b) => a + b, 0) / completions.length);

  const handleGenerate = useCallback(async () => {
    setPhase('generating');
    setGeneration(null);
    setGenerationError(null);
    setIsGenerating(true);
    setGenProgress(5);
    setGenStage('normalizing');

    try {
      const savedDraft = await createDraft({
        ...draft,
        supplement: { messages: chatMessages },
      });
      setGenProgress(15);
      setGenStage('injecting-rules');

      const result = await generateDraft(savedDraft.id);
      setGeneration(result);
      setGenProgress(result.progress);
      setGenStage(result.currentStage);
      setPhase('result');
    } catch (error) {
      setGenerationError(messageFromError(error));
      setGenProgress(0);
      setGenStage(null);
      setPhase('result');
    } finally {
      setIsGenerating(false);
    }
  }, [chatMessages, draft]);

  const handleBackToForm = useCallback(() => {
    setPhase('form');
    setGenProgress(0);
    setGenStage(null);
    setGenerationError(null);
  }, []);

  const handleNewDraft = useCallback(() => {
    resetDraft();
    setChatMessages([]);
    setCurrentStep(0);
    setGeneration(null);
    setGenerationError(null);
    setPhase('form');
  }, [resetDraft]);

  const handleSendMessage = useCallback((text: string) => {
    const userMsg: ChatMessage = {
      id: `msg_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    setChatMessages((prev) => {
      const messages = [...prev, userMsg];
      updateDraft({ supplement: { messages } });
      return messages;
    });
  }, [updateDraft]);

  if (phase === 'form') {
    const stepKey = STEP_KEYS[currentStep];

    return (
      <div className="flex flex-col flex-1">
        <section className="mb-5">
          <p className="mb-2 text-[12px] tracking-[0.22em] uppercase text-muted-foreground">NovaFDE</p>
          <h1 className="text-[var(--text-2xl)] font-semibold leading-tight">创建新 Skill</h1>
        </section>

        <StepIndicator
          steps={steps}
          currentStep={currentStep}
          onStepClick={setCurrentStep}
          completions={completions}
        />

        <div className="grid grid-cols-[1fr_var(--sidebar-width)] gap-3 items-stretch flex-1 min-h-[calc(100dvh-160px)]">
          <Card className="flex flex-col bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
            <div className="mb-5">
              <h2 className="text-[var(--text-lg)] font-semibold mb-1">{STEP_LABELS[stepKey]}</h2>
              <p className="text-[var(--text-sm)] text-muted-foreground leading-normal">{STEP_DESCRIPTIONS[currentStep]}</p>
            </div>

            <div className="flex-1 flex flex-col">
              {stepKey === 'basic' && <BasicStep draft={draft} onUpdate={updateDraft} />}
              {stepKey === 'trigger' && <TriggerStep draft={draft} onUpdateTrigger={updateTrigger} />}
              {stepKey === 'workflow' && <WorkflowStep draft={draft} onUpdateWorkflow={updateWorkflow} />}
              {stepKey === 'context' && <ContextStep draft={draft} onUpdateContext={updateContext} />}
              {stepKey === 'knowledge' && <KnowledgeStep draft={draft} onUpdateKnowledge={updateKnowledge} />}
              {stepKey === 'output' && <OutputStep draft={draft} onUpdateOutputControl={updateOutputControl} />}
              {stepKey === 'supplement' && (
                <SupplementStep messages={chatMessages} onSendMessage={handleSendMessage} />
              )}
            </div>

            <div className="flex justify-between items-center mt-auto pt-4 border-t border-panel-border">
              <Button
                variant="outline"
                onClick={() => setCurrentStep((s) => Math.max(0, s - 1))}
                disabled={currentStep === 0}
                type="button"
                className={cn(currentStep === 0 && 'opacity-30')}
              >
                上一步
              </Button>
              {currentStep < STEP_KEYS.length - 1 ? (
                <Button onClick={() => setCurrentStep((s) => s + 1)} type="button">
                  下一步
                </Button>
              ) : (
                <Button onClick={handleGenerate} type="button" disabled={isGenerating}>
                  {isGenerating ? '生成中...' : '开始生成'}
                </Button>
              )}
            </div>
          </Card>

          <div className="sticky top-7 flex flex-col gap-3 self-stretch">
            <Card className="p-4 bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md">
              <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">信息完整度</p>
              <div className="flex flex-col gap-2 mt-2">
                {STEP_KEYS.map((key, i) => (
                  <div key={key} className="flex items-center gap-2">
                    <span className="text-[var(--text-sm)] text-muted-foreground min-w-[48px]">{STEP_LABELS[key].slice(0, 2)}</span>
                    <div className="flex-1 h-[3px] rounded-full bg-white/6 overflow-hidden">
                      <div
                        className="h-full rounded-full transition-all duration-300"
                        style={{
                          width: `${completions[i]}%`,
                          background: completions[i] >= 80 ? 'var(--color-success)' : 'var(--color-accent)',
                        }}
                      />
                    </div>
                    <span className="text-[12px] text-tertiary whitespace-nowrap min-w-[28px] text-right font-mono">{completions[i]}%</span>
                  </div>
                ))}
              </div>
            </Card>

            <Card className="p-4 bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md">
              <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">总完成度</p>
              <Progress value={overallCompletion} className="h-1.5 mt-2" />
              <p className="text-[var(--text-xl)] font-semibold text-center mt-2">{overallCompletion}%</p>
            </Card>
          </div>
        </div>
      </div>
    );
  }

  if (phase === 'generating') {
    return (
      <div className="flex flex-col items-center justify-center flex-1">
        <section className="mb-5 text-center w-full">
          <p className="mb-2 text-[12px] tracking-[0.22em] uppercase text-muted-foreground">NovaFDE</p>
          <h1 className="text-[var(--text-2xl)] font-semibold leading-tight">正在生成</h1>
        </section>
        <Card className="max-w-[560px] w-full bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
          <PipelineProgress currentStage={genStage} progress={genProgress} />
        </Card>
      </div>
    );
  }

  if (generationError && !generation) {
    return (
      <div className="flex flex-col flex-1">
        <section className="mb-5">
          <p className="mb-2 text-[12px] tracking-[0.22em] uppercase text-muted-foreground">NovaFDE</p>
          <h1 className="text-[var(--text-2xl)] font-semibold leading-tight">生成失败</h1>
        </section>
        <Card className="max-w-[720px] bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
          <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-4">请求错误</p>
          <Alert className="mt-3 border-warning-border bg-warning-dim text-warning">
            <AlertDescription>{generationError}</AlertDescription>
          </Alert>
          <div className="flex justify-between items-center mt-auto pt-4 border-t border-panel-border">
            <Button variant="outline" onClick={handleBackToForm} type="button">返回编辑</Button>
          </div>
        </Card>
      </div>
    );
  }

  const result = generation;
  if (!result) return null;

  return (
    <div className="flex flex-col flex-1">
      <section className="mb-5">
        <p className="mb-2 text-[12px] tracking-[0.22em] uppercase text-muted-foreground">NovaFDE</p>
        <h1 className="text-[var(--text-2xl)] font-semibold leading-tight">{result.status === 'success' ? '生成完成' : '生成未通过'}</h1>
      </section>

      <div className="grid grid-cols-[1fr_var(--sidebar-width)] gap-3 items-start flex-1">
        <div className="flex flex-col gap-3">
          <Card className="bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
            <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-4">文件结构</p>
            <div className="rounded-[var(--radius-md)] bg-gradient-radial from-surface-up to-transparent p-5">
              {result.files.length > 0 ? <FileTree files={result.files} /> : <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">暂无文件输出</div>}
            </div>
          </Card>

          <Card className="bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
            <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-4">SKILL.md 预览</p>
            <pre className="p-4 rounded-[var(--radius-md)] bg-[#020202] border border-white/6 text-[#f5f5f5] font-mono text-[var(--text-sm)] leading-[1.7] whitespace-pre-wrap overflow-x-auto max-h-[400px] overflow-y-auto m-0">{result.skillMd || '暂无预览'}</pre>
          </Card>

          <Card className="bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
            <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-4">校验报告</p>
            {result.validation.length > 0 ? <ValidationReport items={result.validation} /> : <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">暂无校验项</div>}
          </Card>

          {result.errorMessage && (
            <Alert className="border-warning-border bg-warning-dim text-warning">
              <AlertDescription>{result.errorMessage}</AlertDescription>
            </Alert>
          )}

          <div className="flex gap-2">
            <Button variant="outline" onClick={handleBackToForm} type="button">返回编辑</Button>
            <Button variant="destructive" onClick={handleNewDraft} type="button">新建草稿</Button>
          </div>
        </div>

        <div className="sticky top-7 flex flex-col gap-3 self-stretch">
          {result.status === 'success' && result.downloadInfo && (
            <DownloadCard info={result.downloadInfo} onDownload={() => window.location.assign(toGenerationDownloadUrl(result.id))} />
          )}

          <Card className="p-4 bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md">
            <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">生成统计</p>
            <div className="flex flex-col gap-2 mt-2">
              <div className="flex justify-between text-[var(--text-sm)] py-1">
                <span className="text-muted-foreground">校验通过</span>
                <span className="text-success">{result.validation.filter((v) => v.level === 'pass').length} 项</span>
              </div>
              <div className="flex justify-between text-[var(--text-sm)] py-1">
                <span className="text-muted-foreground">警告</span>
                <span className="text-warning">{result.warnings} 项</span>
              </div>
              <div className="flex justify-between text-[var(--text-sm)] py-1">
                <span className="text-muted-foreground">阻塞</span>
                <span className="text-error">{result.blockingIssues} 项</span>
              </div>
              <div className="flex justify-between text-[var(--text-sm)] py-1">
                <span className="text-muted-foreground">文件数</span>
                <span>{result.downloadInfo?.fileCount || result.files.length}</span>
              </div>
            </div>
          </Card>

          {result.downloadInfo && (
            <Card className="p-4 bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md">
              <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">支持平台</p>
              <div className="flex flex-wrap gap-2 mt-2">
                {result.downloadInfo.platforms.map((platform) => (
                  <span key={platform} className="bg-accent-dim border border-accent-border text-accent rounded-full py-1.5 px-3.5 text-[var(--text-sm)]">{platform}</span>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}