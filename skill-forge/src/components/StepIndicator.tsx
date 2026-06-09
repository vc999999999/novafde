import type { StepKey } from '../data';
import { cn } from '@/lib/utils';

interface Props {
  steps: { key: StepKey; label: string }[];
  currentStep: number;
  onStepClick: (index: number) => void;
  completions: number[];
}

export default function StepIndicator({ steps, currentStep, onStepClick, completions }: Props) {
  return (
    <div className="flex items-center gap-0 mb-6 overflow-x-auto pb-2">
      {steps.map((step, i) => (
        <div key={step.key} style={{ display: 'contents' }}>
          <button
            className={cn(
              'w-7 h-7 rounded-full border flex items-center justify-center text-[var(--text-xs)] shrink-0 cursor-pointer transition-all',
              i < currentStep
                ? 'bg-success border-success text-black'
                : i === currentStep
                  ? 'bg-accent border-accent text-black'
                  : 'border-white/12 bg-surface text-muted-foreground'
            )}
            onClick={() => onStepClick(i)}
            title={step.label}
          >
            {i < currentStep ? '✓' : i + 1}
          </button>
          {i < steps.length - 1 && (
            <div className={cn(
              'flex-1 min-w-5 h-px relative',
              i < currentStep ? 'bg-success' : 'bg-white/8'
            )}>
              <span className="text-[11px] text-tertiary ml-1 whitespace-nowrap">{completions[i]}%</span>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}