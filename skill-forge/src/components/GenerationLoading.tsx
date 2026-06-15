import { LoaderCircle, Square } from 'lucide-react';
import type { GenerationStage, GenerationStageKey } from '../types';
import PipelineProgress from './PipelineProgress';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';


const STAGE_HEADLINES: Partial<Record<GenerationStage, string>> = {
  queued: '正在准备本地生成任务',
  normalizing: '正在整理输入并冻结生成规格',
  'generating-workflow': '正在构建工作流骨架',
  'generating-knowledge': '正在补全知识与文件',
  'generating-quality': '正在建立质量约束',
  'generating-trace': '正在检查并准备打包',
  'injecting-rules': '正在注入质量规则',
  'splitting-workflow': '正在拆分工作流',
  'generating-ir': '正在生成初始工作流',
  'validating-schema': '正在检查结构化输出',
  'rendering-files': '正在渲染 Skill 文件',
  'running-validation-checks': '正在检查 Skill 结构',
  'evaluating-activation': '正在评估触发准确性',
  'evaluating-implementation': '正在评估工作流实现质量',
  'aggregating-scores': '正在汇总质量评分',
  repairing: '正在根据评测结果优化',
  'awaiting-user-input': '等待用户补充信息',
  'selecting-best-candidate': '正在选择最佳版本',
  'quality-gate': '正在检查质量门禁',
  packaging: '正在打包文件',
};

interface Props {
  stage: GenerationStage | null;
  progress: number;
  currentRound: number;
  maxRepairRounds: number;
  stageAttempt?: number;
  stageMaxAttempts?: number;
  completedStages?: GenerationStageKey[];
  stageMessage?: string;
  cancelRequested?: boolean;
  isCancelling?: boolean;
  onCancel?: () => void;
  isFailed?: boolean;
}

export default function GenerationLoading({
  stage,
  progress,
  currentRound,
  maxRepairRounds,
  stageAttempt = 0,
  stageMaxAttempts = 3,
  completedStages = [],
  stageMessage = '',
  cancelRequested = false,
  isCancelling = false,
  onCancel,
  isFailed,
}: Props) {
  const isStagedGeneration = stage?.startsWith('generating-') ?? false;
  const statusLine = stageMessage || (
    currentRound > 0
      ? '质量评测与定向优化正在运行'
      : '初始候选生成与评测'
  );

  return (
    <div className="flex min-w-0 flex-1">
      <Card className="animate-step-in relative w-full overflow-hidden border-panel-border bg-panel p-6 shadow-md">
        <div
          aria-hidden
          className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-accent/70 to-transparent"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -right-20 -top-24 size-64 rounded-full bg-accent/8 blur-3xl"
        />

        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-center gap-3">
            <div className="relative flex size-11 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-accent-border bg-accent-dim">
              <span className="absolute inset-1 animate-ping rounded-[var(--radius-sm)] border border-accent/20 [animation-duration:2.4s]" />
              <LoaderCircle className="relative size-5 animate-spin text-accent" />
            </div>
            <div className="min-w-0">
              <p className="text-[10px] uppercase tracking-[0.2em] text-accent">
                Quality-first generation
              </p>
              <h2 className="mt-1 text-base font-semibold">
                {STAGE_HEADLINES[stage ?? 'queued'] ?? '正在生成专业 Skill'}
              </h2>
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {statusLine}
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            {isStagedGeneration && stageAttempt > 0 && (
              <span className="rounded-full border border-accent-border bg-accent-dim px-2.5 py-1 font-mono text-[11px] text-accent">
                第 {stageAttempt}/{stageMaxAttempts} 次尝试
              </span>
            )}
            {currentRound > 0 && (
              <span className="rounded-full border border-black/10 bg-surface px-2.5 py-1 font-mono text-[11px] text-muted-foreground">
                第 {currentRound}/{maxRepairRounds} 轮优化
              </span>
            )}
          </div>
        </div>

        <div className="relative mt-6 rounded-lg border border-black/8 bg-surface/70 p-4">
          <PipelineProgress
            currentStage={stage}
            progress={progress}
            completedStages={completedStages}
            isFailed={isFailed}
          />
        </div>

        <div className="relative mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-panel-border pt-4">
          <div className="flex items-center gap-3">
            <span className="flex items-end gap-0.5" aria-hidden>
              {[0, 1, 2, 3].map((item) => (
                <span
                  key={item}
                  className="w-0.5 animate-pulse rounded-full bg-accent"
                  style={{
                    height: `${6 + item * 2}px`,
                    animationDelay: `${item * 160}ms`,
                  }}
                />
              ))}
            </span>
            <p className="text-xs text-muted-foreground">
              质量优先，不限制单次任务总预算与总时长
            </p>
          </div>
          {onCancel && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onCancel}
              disabled={cancelRequested || isCancelling}
            >
              <Square className="size-3 fill-current" />
              {cancelRequested || isCancelling ? '正在停止...' : '停止生成'}
            </Button>
          )}
        </div>
      </Card>
    </div>
  );
}
