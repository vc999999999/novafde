import { useCallback, useEffect, useState } from 'react';
import { listHistory, startGeneration } from '../api';
import type {
  HistoryItem,
  HistoryItemStatus,
  ModelConnectionStatus,
} from '../types';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

type StatusStyle = {
  label: string;
  variant: 'secondary' | 'default' | 'outline' | 'destructive';
  dotColor: string;
};

const STATUS_MAP: Record<HistoryItemStatus, StatusStyle> = {
  draft: { label: '草稿', variant: 'secondary', dotColor: 'bg-text-secondary' },
  generating: { label: '生成中', variant: 'default', dotColor: 'bg-accent' },
  validating: { label: '校验中', variant: 'outline', dotColor: 'bg-warning' },
  downloadable: { label: '可下载', variant: 'default', dotColor: 'bg-success' },
  'awaiting-user-input': { label: '待补充', variant: 'outline', dotColor: 'bg-warning' },
  degraded: { label: '低分版本', variant: 'outline', dotColor: 'bg-warning' },
  interrupted: { label: '已中断', variant: 'destructive', dotColor: 'bg-error' },
  failed: { label: '失败', variant: 'destructive', dotColor: 'bg-error' },
};

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : '历史记录加载失败。';
}

export default function HistoryPage({
  connection,
  onOpenGeneration,
  onOpenSettings,
}: {
  connection: ModelConnectionStatus;
  onOpenGeneration: (generationId: string) => void;
  onOpenSettings: () => void;
}) {
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setItems(await listHistory());
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;

    listHistory()
      .then((loadedItems) => {
        if (active) setItems(loadedItems);
      })
      .catch((err: unknown) => {
        if (active) setError(messageFromError(err));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const handleGenerate = useCallback(
    async (draftId: string) => {
      setBusyId(draftId);
      setError(null);
      try {
        await startGeneration(draftId);
        await loadHistory();
      } catch (err) {
        setError(messageFromError(err));
      } finally {
        setBusyId(null);
      }
    },
    [loadHistory],
  );

  return (
    <div className="flex flex-1 flex-col">
      <section className="mb-5">
        <p className="mb-2 text-[length:var(--text-xs)] tracking-[0.22em] uppercase text-text-secondary">
          NovaFDE
        </p>
        <h1 className="text-[length:var(--text-2xl)] leading-tight font-semibold">
          历史记录
        </h1>
      </section>

      {error && (
        <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {connection.status !== 'connected' && (
        <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span>模型未连接，仍可查看历史结果，但不能从草稿启动新任务。</span>
            <Button type="button" size="sm" variant="outline" onClick={onOpenSettings}>
              打开设置
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {loading && (
        <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground text-[length:var(--text-base)]">
          正在从后端加载历史记录...
        </div>
      )}

      {!loading && items.length === 0 && (
        <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground text-[length:var(--text-base)]">
          暂无历史记录
        </div>
      )}

      <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-3 max-md:grid-cols-1">
        {items.map((item) => {
          const statusInfo = STATUS_MAP[item.status];
          const isBusy = busyId === item.id;
          const opensExistingGeneration = item.status !== 'draft' && item.generationId;
          const actionLabel = item.status === 'draft'
            ? connection.status === 'connected' ? '开始生成' : '请先连接模型'
            : item.status === 'awaiting-user-input'
              ? '继续补充'
              : item.status === 'generating' || item.status === 'validating'
                ? '查看进度'
                : '查看结果';

          /* Separate per-status Badge styles with custom CSS var colors */
          const badgeClassMap: Record<HistoryItemStatus, string> = {
            draft: 'bg-white/5 text-text-secondary border-white/8',
            generating: 'bg-accent-dim text-accent border-accent-border',
            validating: 'bg-warning-dim text-warning border-warning-border',
            downloadable: 'bg-success-dim text-success border-success-border',
            'awaiting-user-input': 'bg-warning-dim text-warning border-warning-border',
            degraded: 'bg-warning-dim text-warning border-warning-border',
            interrupted: 'bg-error-dim text-error border-error-border',
            failed: 'bg-error-dim text-error border-error-border',
          };

          const dotClassMap: Record<HistoryItemStatus, string> = {
            draft: 'bg-text-secondary',
            generating: 'bg-accent animate-pulse',
            validating: 'bg-warning',
            downloadable: 'bg-success',
            'awaiting-user-input': 'bg-warning',
            degraded: 'bg-warning',
            interrupted: 'bg-error',
            failed: 'bg-error',
          };

          return (
            <Card
              key={item.id}
              className="cursor-pointer transition-[transform,border-color] duration-180 ease-in-out hover:-translate-y-0.5 hover:border-panel-hover"
            >
              <CardHeader className="pb-0">
                <div className="flex w-full items-start justify-between gap-3">
                  <div className="min-w-0">
                    <CardTitle className="text-[length:var(--text-md)] leading-tight">
                      {item.displayName}
                    </CardTitle>
                    <p className="mt-1 text-[length:var(--text-sm)] font-mono text-text-secondary">
                      {item.name}
                    </p>
                  </div>
                  <Badge
                    variant={statusInfo.variant}
                    className={cn(
                      'shrink-0 gap-1.5 text-[length:var(--text-xs)] tracking-widest uppercase',
                      badgeClassMap[item.status],
                    )}
                  >
                    <span
                      className={cn(
                        'inline-block size-1.5 shrink-0 rounded-full',
                        dotClassMap[item.status],
                      )}
                    />
                    {statusInfo.label}
                  </Badge>
                </div>
              </CardHeader>

              <CardContent>
                <div className="mb-3 flex flex-wrap gap-2">
                  {item.platforms.map((platform) => (
                    <span
                      key={platform}
                      className="pointer-events-none rounded-full border border-white/12 bg-surface px-2 py-1 text-[12px] text-text-secondary"
                    >
                      {platform}
                    </span>
                  ))}
                </div>

                <div className="flex justify-between text-[length:var(--text-sm)] text-text-secondary">
                  <span>创建: {item.createdAt}</span>
                  <span>更新: {item.updatedAt}</span>
                </div>

                <Button
                  variant={item.status === 'failed' ? 'destructive' : 'default'}
                  className="mt-3 w-full"
                  type="button"
                  onClick={() => {
                    if (opensExistingGeneration) {
                      onOpenGeneration(item.generationId as string);
                    } else {
                      void handleGenerate(item.id);
                    }
                  }}
                  disabled={
                    isBusy
                    || (item.status === 'draft' && connection.status !== 'connected')
                  }
                >
                  {isBusy ? '生成中...' : actionLabel}
                </Button>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <p className="mt-8 text-center text-[length:var(--text-sm)] text-text-tertiary">
        共 {items.length} 条记录 / 数据来自本地后端
      </p>
    </div>
  );
}
