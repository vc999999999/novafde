import { CircleAlert, LoaderCircle, Plug, PlugZap } from 'lucide-react';
import type { ModelConnectionStatus as Connection } from '../types';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';


const LABELS = {
  unconfigured: '模型未配置',
  connecting: '模型连接中',
  connected: '模型已连接',
  disconnected: '模型未连接',
  error: '模型连接错误',
} as const;

export default function ModelConnectionStatus({
  connection,
  onOpenSettings,
}: {
  connection: Connection;
  onOpenSettings: () => void;
}) {
  const Icon = connection.status === 'connected'
    ? PlugZap
    : connection.status === 'connecting'
      ? LoaderCircle
      : connection.status === 'error'
        ? CircleAlert
        : Plug;
  const model = connection.generationProvider?.model;

  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={onOpenSettings}
      aria-label={`${LABELS[connection.status]}${model ? ` ${model}` : ''}`}
      title={connection.message}
      className={cn(
        'h-8 max-w-[260px] gap-2 px-3 text-xs',
        connection.status === 'connected' && 'border-success-border text-success',
        connection.status === 'error' && 'border-error-border text-error',
        connection.status === 'connecting' && 'border-accent-border text-accent',
      )}
    >
      <Icon className={cn('size-3.5 shrink-0', connection.status === 'connecting' && 'animate-spin')} />
      <span className="whitespace-nowrap">{LABELS[connection.status]}</span>
      {model && <span className="truncate font-mono text-[11px] text-muted-foreground">{model}</span>}
    </Button>
  );
}
