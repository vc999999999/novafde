import { useEffect, useState, type CSSProperties } from 'react';
import { getDiagnosticMetrics, listErrorPatterns, listRules } from '../api';
import PageHeader from '../components/PageHeader';
import type { DiagnosticMetrics, ErrorPattern, QualityRule } from '../types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

/* Same panel style as LocalRunPage cards: subtle border + soft gradient */
const PANEL_CARD_CLASS =
  'bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md';

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : '规则加载失败。';
}

export default function RulesPage() {
  const [rules, setRules] = useState<QualityRule[]>([]);
  const [metrics, setMetrics] = useState<DiagnosticMetrics | null>(null);
  const [patterns, setPatterns] = useState<ErrorPattern[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const categories = [...new Set(rules.map((rule) => rule.category))];

  useEffect(() => {
    let active = true;

    async function loadRules() {
      setLoading(true);
      setError(null);
      try {
        const [loadedRules, loadedMetrics, loadedPatterns] = await Promise.all([
          listRules(),
          getDiagnosticMetrics(),
          listErrorPatterns(),
        ]);
        if (active) {
          setRules(loadedRules);
          setMetrics(loadedMetrics);
          setPatterns(loadedPatterns);
        }
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
      <PageHeader
        title="质量规则"
        sub={loading ? '加载中' : `${rules.length} 条规则 · 生成时自动应用`}
      />

      {error && (
        <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && (
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <Card key={i} className={cn(PANEL_CARD_CLASS, 'animate-pulse gap-2 p-4')}>
              <div className="h-3 w-1/2 rounded bg-white/5" />
              <div className="h-6 w-1/3 rounded bg-white/8" />
            </Card>
          ))}
        </div>
      )}

      {metrics && (
        <section className="mb-7">
          <h2 className="mb-3 text-[length:var(--text-md)] font-semibold">本地质量诊断</h2>
          {metrics.alerts.map((alert) => (
            <Alert key={alert} className="mb-2 border-warning-border bg-warning-dim text-warning">
              <AlertDescription>{alert}</AlertDescription>
            </Alert>
          ))}
          <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
            {[
              ['任务数', metrics.runCount],
              ['首轮通过率', `${metrics.firstRoundStrictPassRate}%`],
              ['最终通过率', `${metrics.finalStrictPassRate}%`],
              ['降级率', `${metrics.degradedDeliveryRate}%`],
              ['技术失败率', `${metrics.technicalFailureRate}%`],
              ['平均修复轮次', metrics.averageRepairRounds],
              ['平均提分', metrics.averageScoreImprovement],
              ['补充触发率', `${metrics.supplementPromptRate}%`],
            ].map(([label, value], index) => (
              <Card
                key={label}
                className={cn(PANEL_CARD_CLASS, 'animate-step-in p-4')}
                style={{ '--enter-delay': `${index * 30}ms` } as CSSProperties}
              >
                <p className="text-xs text-muted-foreground">{label}</p>
                <p data-numeric className="mt-1 font-mono text-lg font-semibold">{value}</p>
              </Card>
            ))}
          </div>

          {Object.keys(metrics.criterionAverageScores).length > 0 && (
            <div className="mt-3">
              <h3 className="mb-2 text-sm font-semibold">评分项均值</h3>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                {Object.entries(metrics.criterionAverageScores).map(([criterion, score]) => (
                  <Card key={criterion} className={cn(PANEL_CARD_CLASS, 'p-3')}>
                    <p className="truncate text-xs text-muted-foreground" title={criterion}>
                      {criterion}
                    </p>
                    <p className="mt-1 font-mono text-base font-semibold">{Math.round(score)}</p>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {Object.keys(metrics.models).length > 0 && (
            <div className="mt-3">
              <h3 className="mb-2 text-sm font-semibold">模型表现</h3>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {Object.entries(metrics.models).map(([model, modelMetrics]) => (
                  <Card key={model} className={cn(PANEL_CARD_CLASS, 'p-4')}>
                    <p className="truncate font-mono text-sm font-semibold" title={model}>
                      {model}
                    </p>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
                      <span>调用 {modelMetrics.calls}</span>
                      <span>通过 {modelMetrics.strictPassRate}%</span>
                      <span>P95 {modelMetrics.p95LatencyMs}ms</span>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </section>
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
                <Card key={rule.id} className={cn(PANEL_CARD_CLASS, 'py-4 transition-colors duration-200 hover:border-white/15')}>
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
                    <p className="m-0 text-[length:var(--text-sm)] leading-relaxed text-text-secondary">
                      {rule.description}
                    </p>
                    <p className="mt-1 font-mono text-[12px] text-text-tertiary">{rule.id}</p>
                  </CardContent>
                </Card>
              ))}
          </div>
        </div>
      ))}

      {patterns.length > 0 && (
        <section className="mt-2">
          <h2 className="mb-3 text-[length:var(--text-md)] font-semibold">高频易错点</h2>
          <div className="flex flex-col gap-2">
            {patterns.slice(0, 10).map((pattern) => (
              <Card key={pattern.id} className={cn(PANEL_CARD_CLASS, 'p-4')}>
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">{pattern.criterion}</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                      {pattern.triggerConditions[0]}
                    </p>
                    <p className="mt-2 text-xs text-accent">{pattern.suggestedFix}</p>
                  </div>
                  <Badge variant="outline" className="shrink-0">
                    {pattern.occurrenceCount} 次
                  </Badge>
                </div>
              </Card>
            ))}
            {patterns.length > 10 && (
              <p className="text-xs text-muted-foreground text-center mt-2">
                共 {patterns.length} 条，当前显示前 10 条
              </p>
            )}
          </div>
        </section>
      )}

    </div>
  );
}
