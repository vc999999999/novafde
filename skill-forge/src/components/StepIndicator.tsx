import { Fragment } from 'react';
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
    <div className="mb-6 flex items-center gap-2 overflow-x-auto pb-2">
      {steps.map((step, i) => {
        const state = i < currentStep ? 'done' : i === currentStep ? 'active' : 'todo';
        return (
          <Fragment key={step.key}>
            <button
              type="button"
              onClick={() => onStepClick(i)}
              aria-current={state === 'active' ? 'step' : undefined}
              className={cn(
                'flex shrink-0 cursor-pointer items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3 text-[13px] transition-colors',
                state === 'active'
                  ? 'border-accent-border bg-accent-dim text-foreground'
                  : state === 'done'
                    ? 'border-success-border bg-success-dim text-foreground'
                    : 'border-white/10 bg-surface text-muted-foreground hover:border-white/20 hover:text-foreground',
              )}
            >
              <span
                className={cn(
                  'flex size-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold',
                  state === 'active'
                    ? 'bg-accent text-black'
                    : state === 'done'
                      ? 'bg-success text-black'
                      : 'bg-white/8 text-muted-foreground',
                )}
              >
                {state === 'done' ? '✓' : i + 1}
              </span>
              <span className="whitespace-nowrap">{step.label}</span>
              <span className="whitespace-nowrap font-mono text-[11px] text-muted-foreground">
                {completions[i]}%
              </span>
            </button>
            {i < steps.length - 1 && (
              <div
                aria-hidden
                className={cn('h-px min-w-3 flex-1', i < currentStep ? 'bg-success/40' : 'bg-white/8')}
              />
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
