import { Fragment } from 'react';
import { Check } from 'lucide-react';
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
                'flex shrink-0 cursor-pointer items-center gap-2 rounded-full border py-1.5 pl-1.5 pr-3 text-[13px] transition-all duration-200 active:scale-[0.97]',
                state === 'active'
                  ? 'border-accent-border bg-accent-dim text-foreground shadow-[0_0_24px_rgba(108,156,255,0.22)]'
                  : state === 'done'
                    ? 'border-success-border bg-success-dim text-foreground hover:border-success/40 hover:-translate-y-px'
                    : 'border-white/10 bg-surface text-muted-foreground hover:-translate-y-px hover:border-white/20 hover:text-foreground',
              )}
            >
              <span
                className={cn(
                  'flex size-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold transition-colors duration-200',
                  state === 'active'
                    ? 'bg-accent text-black animate-[pulse-shadow_2.4s_ease-in-out_infinite]'
                    : state === 'done'
                      ? 'bg-success text-black'
                      : 'bg-white/8 text-muted-foreground',
                )}
              >
                {state === 'done'
                  ? <Check className="size-3.5 animate-[check-pop_0.3s_ease-out]" strokeWidth={3} />
                  : i + 1}
              </span>
              <span className="whitespace-nowrap">{step.label}</span>
              <span
                data-numeric
                className={cn(
                  'whitespace-nowrap font-mono text-[11px] transition-colors duration-200',
                  completions[i] >= 100 ? 'text-success' : 'text-tertiary',
                )}
              >
                {completions[i]}%
              </span>
            </button>
            {i < steps.length - 1 && (
              <div aria-hidden className="relative h-0.5 min-w-3 flex-1 overflow-hidden rounded-full bg-white/8">
                <div
                  className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-success/60 to-success/35 transition-[width] duration-500 ease-out"
                  style={{ width: i < currentStep ? '100%' : '0%' }}
                />
              </div>
            )}
          </Fragment>
        );
      })}
    </div>
  );
}
