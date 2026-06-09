import type { ValidationItem } from '../types';
import { cn } from '@/lib/utils';

interface Props {
  items: ValidationItem[];
}

export default function ValidationReport({ items }: Props) {
  const passed = items.filter((i) => i.level === 'pass').length;
  const warnings = items.filter((i) => i.level === 'warning').length;
  const blocking = items.filter((i) => i.level === 'blocking').length;

  return (
    <div>
      <div className="flex gap-4 mb-4">
        <div className="flex items-center gap-1.5 text-[var(--text-sm)]">
          <span className="w-2 h-2 rounded-full shrink-0 bg-success" />
          <span className="text-success">{passed} 通过</span>
        </div>
        {warnings > 0 && (
          <div className="flex items-center gap-1.5 text-[var(--text-sm)]">
            <span className="w-2 h-2 rounded-full shrink-0 bg-warning" />
            <span className="text-warning">{warnings} 警告</span>
          </div>
        )}
        {blocking > 0 && (
          <div className="flex items-center gap-1.5 text-[var(--text-sm)]">
            <span className="w-2 h-2 rounded-full shrink-0 bg-error" />
            <span className="text-error">{blocking} 阻塞</span>
          </div>
        )}
      </div>
      <div className="flex flex-col gap-2">
        {items.map((item) => (
          <div key={item.id} className="flex items-start gap-3 p-3 px-4 rounded-[var(--radius-md)] border border-white/6 bg-surface">
            <div className={cn(
              'w-2 h-2 rounded-full shrink-0 mt-[5px]',
              item.level === 'pass' && 'bg-success',
              item.level === 'warning' && 'bg-warning',
              item.level === 'blocking' && 'bg-error',
            )} />
            <div className="flex-1 min-w-0">
              <div className="text-[var(--text-base)] font-medium mb-0.5">
                {item.title}
                <span className="text-[var(--text-xs)] tracking-wide text-tertiary ml-2">{item.ruleId}</span>
              </div>
              <div className="text-[var(--text-sm)] text-muted-foreground leading-[var(--leading-normal)]">{item.description}</div>
              {item.suggestion && (
                <div className="text-[var(--text-sm)] text-accent mt-1">{item.suggestion}</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}