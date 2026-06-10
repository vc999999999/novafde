import type { QualityEvaluationReport } from '../types';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';


function Score({ label, value }: { label: string; value: number | null }) {
  const score = value ?? 0;
  return (
    <div className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={cn(
        'font-mono text-sm',
        value === null ? 'text-muted-foreground' : score >= 90 ? 'text-emerald-500' : score >= 70 ? 'text-amber-500' : 'text-red-500',
      )}>
        {value === null ? '--' : Math.round(value)}
      </span>
    </div>
  );
}

export default function QualityScorePanel({ report }: { report: QualityEvaluationReport }) {
  return (
    <Card className="border-panel-border bg-panel p-4 shadow-md">
      <div className="mb-2 flex items-center justify-between">
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">质量评分</p>
        <span className={cn(
          'rounded-full border px-2 py-1 text-[11px]',
          report.passedStrictGate
            ? 'border-success-border bg-success-dim text-success'
            : 'border-warning-border bg-warning-dim text-warning',
        )}>
          {report.passedStrictGate ? '高质量通过' : '需要检查'}
        </span>
      </div>
      <Score label="Overall" value={report.overallScore} />
      <Score label="Validation" value={report.validationScore} />
      <Score label="Activation" value={report.activationScore} />
      <Score label="Implementation" value={report.implementationScore} />
      {report.issues.length > 0 && (
        <div className="mt-3 border-t border-panel-border pt-3">
          <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">主要问题</p>
          <div className="space-y-2">
            {report.issues.slice(0, 3).map((issue) => (
              <div key={issue.issueId} className="text-xs leading-relaxed">
                <p className="font-medium">{issue.criterion}</p>
                <p className="text-muted-foreground">{issue.reason}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
}
