import { LoaderCircle } from 'lucide-react';
import type { GenerationStage } from '../types';
import PipelineProgress from './PipelineProgress';
import { Card } from '@/components/ui/card';


const STAGE_HEADLINES: Partial<Record<GenerationStage, string>> = {
  queued: '正在准备本地生成任务',
  normalizing: '正在整理输入',
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

export default function GenerationLoading({
  stage,
  progress,
  currentRound,
  maxRepairRounds,
  isFailed,
}: {
  stage: GenerationStage | null;
  progress: number;
  currentRound: number;
  maxRepairRounds: number;
  isFailed?: boolean;
}) {
  return (
    <div className="flex min-h-[calc(100dvh-150px)] flex-1 items-center justify-center">
      <Card className="animate-step-in w-full max-w-[620px] border-panel-border bg-panel p-6 shadow-md">
        <div className="mb-5 flex items-center gap-3">
          <div className="flex size-10 shrink-0 items-center justify-center rounded-[var(--radius-sm)] border border-accent-border bg-accent-dim">
            <LoaderCircle className="size-5 animate-spin text-accent" />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-semibold">
              {STAGE_HEADLINES[stage ?? 'queued'] ?? '正在生成专业 Skill'}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              {currentRound > 0
                ? `第 ${currentRound}/${maxRepairRounds} 轮优化`
                : '初始候选生成与评测'}
            </p>
          </div>
        </div>
        <PipelineProgress currentStage={stage} progress={progress} isFailed={isFailed} />
      </Card>
    </div>
  );
}
