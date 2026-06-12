import type { CSSProperties } from 'react';
import type { GenerationStage } from '../types';
import { STAGES } from '../data';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

interface Props {
  currentStage: GenerationStage | null;
  progress: number;
  isFailed?: boolean;
}

export default function PipelineProgress({ currentStage, progress, isFailed }: Props) {
  const stageIdx = currentStage ? STAGES.findIndex((s) => s.key === currentStage) : -1;

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <p className="text-[11px] tracking-[0.18em] uppercase text-muted-foreground mb-0">生成进度</p>
        <span className="text-sm font-mono text-accent">
          {progress}%
        </span>
      </div>
      <Progress
        value={progress}
        className={cn(
          'h-1 mb-5',
          isFailed ? '[&>div]:bg-error' : progress >= 100 ? '[&>div]:bg-success' : ''
        )}
      />
      <div className="flex flex-col">
        {STAGES.map((stage, i) => {
          const isCompleted = i < stageIdx || progress >= 100;
          const isActive = i === stageIdx && !isFailed;
          const isFailedStage = isFailed && i === stageIdx;

          return (
            <div
              key={stage.key}
              className={cn(
                'animate-step-in flex items-start gap-3 py-3 relative',
                i < STAGES.length - 1 && 'after:content-[""] after:absolute after:left-[13px] after:top-10 after:bottom-0 after:w-px after:transition-colors after:duration-500',
                i < STAGES.length - 1 && (isCompleted ? 'after:bg-success' : 'after:bg-white/8')
              )}
              style={{ '--enter-delay': `${i * 40}ms` } as CSSProperties}
            >
              <div className={cn(
                'w-7 h-7 rounded-full border flex items-center justify-center shrink-0 text-xs font-medium transition-all duration-300',
                isCompleted && 'bg-success border-success text-black',
                isActive && 'bg-accent border-accent text-black animate-[pulse-shadow_2s_ease-in-out_infinite]',
                isFailedStage && 'bg-error border-error text-black',
                !isCompleted && !isActive && !isFailedStage && 'border-white/12 bg-surface text-muted-foreground'
              )}>
                {isCompleted ? <span className="animate-[check-pop_0.3s_ease-out]">✓</span> : i + 1}
              </div>
              <div className="flex-1 min-w-0">
                <p className={cn(
                  'text-sm font-medium leading-tight',
                  isActive && 'text-accent',
                  isFailedStage && 'text-error',
                  !isActive && !isFailedStage && 'text-foreground'
                )}>
                  {stage.label}
                </p>
                <p className="text-xs text-muted-foreground mt-0.5">{stage.sub}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}