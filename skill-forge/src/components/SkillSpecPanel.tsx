import type { ReactNode } from 'react';
import type { SkillSpecResponse } from '../types';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';


function Section({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-t border-panel-border pt-3 first:border-t-0 first:pt-0">
      <p className="mb-2 text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
        {title}
      </p>
      {children}
    </section>
  );
}

function List({ items }: { items: string[] }) {
  if (items.length === 0) {
    return <p className="text-xs text-muted-foreground">无</p>;
  }
  return (
    <ol className="space-y-1.5 text-xs leading-relaxed">
      {items.map((item, index) => (
        <li key={`${index}-${item}`} className="flex gap-2">
          <span className="font-mono text-muted-foreground">{index + 1}.</span>
          <span>{item}</span>
        </li>
      ))}
    </ol>
  );
}

export default function SkillSpecPanel({
  response,
  unavailable = false,
  compact = false,
  defaultOpen = false,
  error = null,
  className,
}: {
  response: SkillSpecResponse | null;
  unavailable?: boolean;
  /** 紧凑模式：内容区限高滚动，默认折叠（可用 defaultOpen 覆盖展开状态） */
  compact?: boolean;
  defaultOpen?: boolean;
  error?: string | null;
  className?: string;
}) {
  if (!response) {
    if (error) {
      return (
        <Card className={cn('border-panel-border bg-panel p-4 shadow-md', className)}>
          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            生成规格
          </p>
          <p className="mt-2 text-sm text-muted-foreground">{error}</p>
        </Card>
      );
    }
    if (!unavailable) return null;
    return (
      <Card className={cn('border-panel-border bg-panel p-4 shadow-md', className)}>
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          生成规格
        </p>
        <p className="mt-2 text-sm">此历史版本无 SDD 规格</p>
      </Card>
    );
  }

  const spec = response.current;
  const filePolicies = [
    spec.fileContract.needsReferences && 'references',
    spec.fileContract.needsScripts && 'scripts',
    spec.fileContract.needsAssets && 'assets',
  ].filter((item): item is string => Boolean(item));

  return (
    <Card className={cn('border-accent-border bg-panel p-4 shadow-md', className)}>
      <details open={defaultOpen || !compact}>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              生成规格
            </p>
            <p className="mt-1 text-sm font-semibold">Revision {response.revision}</p>
          </div>
          <span className="rounded-full border border-accent-border bg-accent-dim px-2 py-1 font-mono text-[10px] text-accent">
            {response.sha256.slice(0, 10)}
          </span>
        </summary>

        <div className={cn('mt-4 space-y-3', compact && !defaultOpen && 'max-h-[55vh] overflow-auto pr-1')}>
          <Section title="触发契约">
            <p className="text-xs leading-relaxed">{spec.activationContract.usage}</p>
            <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
              目标：{spec.activationContract.desiredOutcome}
            </p>
          </Section>

          <Section title="工作流">
            <List items={spec.workflowStages.map((item) => item.statement)} />
          </Section>

          <Section title="增量知识">
            <List items={spec.incrementalKnowledge} />
          </Section>

          {(spec.userSupplements ?? []).length > 0 && (
            <Section title="用户补充">
              <List
                items={(spec.userSupplements ?? []).map((item) => item.statement)}
              />
            </Section>
          )}

          <Section title="硬限制">
            <List items={spec.hardRestrictions} />
          </Section>

          <Section title="文件策略">
            <p className="text-xs">
              {filePolicies.length > 0 ? filePolicies.join(' / ') : '仅 SKILL.md'}
            </p>
          </Section>

          <Section title="验收标准">
            <List items={spec.acceptanceCriteria.map((item) => item.statement)} />
          </Section>

          <Section title="修订信息">
            <p className="break-all font-mono text-[10px] leading-relaxed text-muted-foreground">
              SHA256 {response.sha256}
            </p>
            <p className="mt-1 text-[11px] text-muted-foreground">
              共 {response.revisions.length} 个不可变修订
            </p>
          </Section>
        </div>
      </details>
    </Card>
  );
}
