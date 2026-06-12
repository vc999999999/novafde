import { useEffect, useRef, useState } from 'react';
import { Check } from 'lucide-react';
import type { StepKey } from '../data';
import { cn } from '@/lib/utils';

function useAnimatedNumber(target: number, duration = 650) {
  const [display, setDisplay] = useState(target);
  const displayRef = useRef(target);

  useEffect(() => {
    const from = displayRef.current;
    if (from === target) return;
    let frame: number;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const value = Math.round(from + (target - from) * eased);
      displayRef.current = value;
      setDisplay(value);
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return display;
}

function ProgressRing({ value }: { value: number }) {
  const size = 92;
  const stroke = 5;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const display = useAnimatedNumber(value);
  const complete = value >= 80;

  return (
    <div className="relative" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="rgba(255,255,255,0.07)"
          strokeWidth={stroke}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={complete ? 'var(--color-success)' : 'var(--color-accent)'}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - Math.min(100, value) / 100)}
          className="transition-[stroke-dashoffset,stroke] duration-700 ease-out"
          style={{
            filter: complete
              ? 'drop-shadow(0 0 6px rgba(74, 222, 128, 0.4))'
              : 'drop-shadow(0 0 6px rgba(108, 156, 255, 0.4))',
          }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span data-numeric className="font-mono text-lg font-semibold leading-none">
          {display}%
        </span>
        <span className="mt-1 text-[10px] tracking-[0.16em] text-tertiary">总完成度</span>
      </div>
    </div>
  );
}

interface Props {
  steps: { key: StepKey; label: string }[];
  completions: number[];
  overall: number;
  currentStep: number;
  onStepClick: (index: number) => void;
  className?: string;
}

export default function StepRail({ steps, completions, overall, currentStep, onStepClick, className }: Props) {
  return (
    <aside className={cn('flex flex-col', className)}>
      <nav aria-label="创建步骤" className="flex flex-col">
        {steps.map((step, i) => {
          const state = i < currentStep ? 'done' : i === currentStep ? 'active' : 'todo';
          return (
            <button
              key={step.key}
              type="button"
              onClick={() => onStepClick(i)}
              aria-current={state === 'active' ? 'step' : undefined}
              className={cn(
                'group relative flex cursor-pointer items-start gap-3 rounded-lg px-2 py-3 text-left transition-colors duration-200 hover:bg-white/4',
                i < steps.length - 1
                  && 'after:absolute after:bottom-0 after:left-[21px] after:top-11 after:w-px after:transition-colors after:duration-500',
                i < steps.length - 1 && (state === 'done' ? 'after:bg-success/50' : 'after:bg-white/8'),
              )}
            >
              <span
                className={cn(
                  'flex size-7 shrink-0 items-center justify-center rounded-full border text-[11px] font-semibold transition-all duration-300',
                  state === 'active'
                    ? 'border-accent bg-accent text-black animate-[pulse-shadow_2.4s_ease-in-out_infinite]'
                    : state === 'done'
                      ? 'border-success bg-success text-black'
                      : 'border-white/12 bg-surface text-muted-foreground group-hover:border-white/24',
                )}
              >
                {state === 'done'
                  ? <Check className="size-3.5 animate-[check-pop_0.3s_ease-out]" strokeWidth={3} />
                  : i + 1}
              </span>
              <span className="flex min-w-0 flex-1 flex-col gap-1.5 pt-1">
                <span className="flex items-baseline justify-between gap-2">
                  <span
                    className={cn(
                      'truncate text-[13px] transition-colors duration-200',
                      state === 'active'
                        ? 'font-medium text-foreground'
                        : 'text-muted-foreground group-hover:text-foreground',
                    )}
                  >
                    {step.label}
                  </span>
                  <span
                    data-numeric
                    className={cn(
                      'shrink-0 font-mono text-[11px] transition-colors duration-200',
                      completions[i] >= 100 ? 'text-success' : 'text-tertiary',
                    )}
                  >
                    {completions[i]}%
                  </span>
                </span>
                <span className="h-[2px] w-full overflow-hidden rounded-full bg-white/6">
                  <span
                    className="block h-full rounded-full transition-all duration-500 ease-out"
                    style={{
                      width: `${completions[i]}%`,
                      background: completions[i] >= 80
                        ? 'var(--color-success)'
                        : 'var(--color-accent)',
                    }}
                  />
                </span>
              </span>
            </button>
          );
        })}
      </nav>

      <div className="my-5 border-t border-panel-border" />

      <div className="flex justify-center">
        <ProgressRing value={overall} />
      </div>

      <p className="mt-5 text-[11px] leading-relaxed text-tertiary">
        Agent 生成结构化 Skill IR，经过确定性校验、触发评测和实现评测后，最多定向优化三轮。
      </p>
    </aside>
  );
}
