import { useEffect, useState } from 'react';
import { listRules } from '../api';
import type { QualityRule } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : '规则加载失败。';
}

export default function RulesPage() {
  const [rules, setRules] = useState<QualityRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const categories = [...new Set(rules.map((rule) => rule.category))];

  useEffect(() => {
    let active = true;

    async function loadRules() {
      setLoading(true);
      setError(null);
      try {
        const loadedRules = await listRules();
        if (active) setRules(loadedRules);
      } catch (err) {
        if (active) setError(messageFromError(err));
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadRules();
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="flex flex-1 flex-col">
      <section className="mb-5">
        <p className="mb-2 text-[length:var(--text-xs)] tracking-[0.22em] uppercase text-text-secondary">
          NovaFDE
        </p>
        <h1 className="text-[length:var(--text-2xl)] leading-[var(--leading-tight)] font-semibold">
          质量规则
        </h1>
      </section>

      {error && (
        <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && (
        <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground text-[length:var(--text-base)]">
          正在从后端加载质量规则...
        </div>
      )}

      {!loading && rules.length === 0 && (
        <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground text-[length:var(--text-base)]">
          暂无质量规则
        </div>
      )}

      {categories.map((category) => (
        <div key={category} className="mb-6">
          <h2 className="mb-3 text-[length:var(--text-md)] font-semibold text-accent">
            {category}
          </h2>
          <div className="flex flex-col gap-2">
            {rules
              .filter((rule) => rule.category === category)
              .map((rule) => (
                <Card key={rule.id} className="py-4">
                  <CardHeader className="pb-1">
                    <div className="flex w-full items-start justify-between gap-3">
                      <CardTitle className="text-[length:var(--text-base)] font-semibold leading-tight">
                        {rule.title}
                      </CardTitle>
                      <Badge
                        variant={rule.severity === 'blocking' ? 'destructive' : 'outline'}
                        className={cn(
                          'shrink-0 tracking-widest uppercase text-[length:var(--text-xs)]',
                          rule.severity === 'blocking'
                            ? 'bg-error-dim text-error border-error-border'
                            : 'bg-warning-dim text-warning border-warning-border',
                        )}
                      >
                        {rule.severity === 'blocking' ? '阻塞' : '警告'}
                      </Badge>
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="m-0 text-[length:var(--text-sm)] leading-[var(--leading-relaxed)] text-text-secondary">
                      {rule.description}
                    </p>
                    <p className="mt-1 font-mono text-[12px] text-text-tertiary">{rule.id}</p>
                  </CardContent>
                </Card>
              ))}
          </div>
        </div>
      ))}

      <p className="mt-8 text-center text-[length:var(--text-sm)] text-text-tertiary">
        规则在生成时由后端自动应用于校验流程
      </p>
    </div>
  );
}