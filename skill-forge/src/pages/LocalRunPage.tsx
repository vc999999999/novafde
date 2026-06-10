import { useCallback, useEffect, useState } from 'react';
import { listCliCommands } from '../api';
import type { CliCommandHelp } from '../types';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { cn } from '@/lib/utils';

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text)
      .then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); })
      .catch(() => { /* fallback: clipboard write failed */ });
  }, [text]);

  return (
    <Button variant="outline" size="sm" onClick={handleCopy} type="button" className="shrink-0">
      {copied ? '已复制' : '复制'}
    </Button>
  );
}

function CommandCard({ cmd }: { cmd: CliCommandHelp }) {
  return (
    <Card className="bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-4">
      <div className="flex justify-between items-start gap-3 mb-3">
        <div>
          <h3 className="text-sm font-semibold my-0 mb-1">{cmd.command}</h3>
          <p className="text-xs text-muted-foreground m-0">{cmd.purpose}</p>
        </div>
        <CopyButton text={cmd.command} />
      </div>

      <pre className="p-3 rounded-[var(--radius-md)] bg-[#020202] border border-white/6 text-[#f5f5f5] font-mono text-xs leading-[1.6] whitespace-pre-wrap word-break-all m-0 mb-3">{cmd.command}</pre>

      <div className="flex flex-wrap gap-2 mb-2">
        <Badge className="bg-white/5 text-muted-foreground border border-white/8 text-[11px] tracking-widest uppercase gap-1.5">
          {cmd.repeatable ? '可重复执行' : '一次性'}
        </Badge>
        <Badge className={cn(
          'text-[11px] tracking-widest uppercase gap-1.5',
          cmd.requiresNetwork
            ? 'bg-warning-dim text-warning border border-warning-border'
            : 'bg-success-dim text-success border border-success-border'
        )}>
          {cmd.requiresNetwork ? '需要网络' : '本地执行'}
        </Badge>
        <Badge className={cn(
          'text-[11px] tracking-widest uppercase gap-1.5',
          cmd.dangerLevel === 'high'
            ? 'bg-error-dim text-error border border-error-border'
            : 'bg-white/5 text-muted-foreground border border-white/8'
        )}>
          风险: {cmd.dangerLevel}
        </Badge>
        {cmd.writes.length > 0 && (
          <Badge className="bg-white/5 text-muted-foreground border border-white/8 text-[11px] tracking-widest uppercase gap-1.5">
            写入: {cmd.writes.join(', ')}
          </Badge>
        )}
      </div>

      <div className="mt-2">
        <p className="text-[12px] text-tertiary my-0 mb-1">失败时收集:</p>
        <span className="text-[12px] text-warning bg-warning-dim py-0.5 px-2 rounded-full border border-warning-border">
          {cmd.failureSummary}
        </span>
      </div>
    </Card>
  );
}

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : 'CLI 命令加载失败。';
}

export default function LocalRunPage() {
  const [commands, setCommands] = useState<CliCommandHelp[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;

    async function loadCommands() {
      setLoading(true);
      setError(null);
      try {
        const loadedCommands = await listCliCommands();
        if (active) setCommands(loadedCommands);
      } catch (err) {
        if (active) setError(messageFromError(err));
      } finally {
        if (active) setLoading(false);
      }
    }

    void loadCommands();
    return () => { active = false; };
  }, []);

  const installCmds = commands.filter((command) =>
    command.command.startsWith('sh scripts/')
  );
  const cliCmds = commands.filter((command) =>
    command.command.startsWith('sh skillforge')
  );
  const otherCmds = commands.filter((command) =>
    !command.command.startsWith('sh scripts/') && !command.command.startsWith('sh skillforge')
  );

  return (
    <div className="flex flex-col flex-1">
      <section className="mb-5">
        <p className="mb-2 text-[12px] tracking-[0.22em] uppercase text-muted-foreground">NovaFDE</p>
        <h1 className="text-3xl font-semibold leading-tight">本地运行</h1>
      </section>

      <p className="text-xs text-muted-foreground mb-5 leading-relaxed">
        按以下顺序执行命令来安装、配置和运行 NovaFDE。每条命令均可复制到终端执行。
      </p>

      {error && (
        <Alert className="mb-4 border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">正在从后端加载 CLI 命令...</div>}

      <div className="mb-6">
        <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">Shell 脚本</p>
        <p className="text-xs text-muted-foreground my-0 mb-3">推荐按顺序执行：安装 → 配置模型 → 启动</p>
        <div className="flex flex-col gap-3">
          {installCmds.map((cmd) => (
            <CommandCard key={cmd.command} cmd={cmd} />
          ))}
        </div>
      </div>

      <div className="mb-6">
        <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">CLI 命令</p>
        <p className="text-xs text-muted-foreground my-0 mb-3">NovaFDE 提供的命令行工具，用于诊断、配置和操作</p>
        <div className="flex flex-col gap-3">
          {cliCmds.map((cmd) => (
            <CommandCard key={cmd.command} cmd={cmd} />
          ))}
        </div>
      </div>

      {otherCmds.length > 0 && (
        <div className="mb-6">
          <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">其他命令</p>
          <p className="text-xs text-muted-foreground my-0 mb-3">其他可用命令</p>
          <div className="flex flex-col gap-3">
            {otherCmds.map((cmd) => (
              <CommandCard key={cmd.command} cmd={cmd} />
            ))}
          </div>
        </div>
      )}

      <Card className="bg-gradient-to-b from-white/[0.035] to-white/[0.01] border-panel-border shadow-md p-5">
        <p className="text-[12px] tracking-[0.18em] uppercase text-muted-foreground mb-2">快速参考</p>
        <div className="flex flex-col gap-2 mt-2">
          <div className="flex justify-between text-xs py-1">
            <span className="text-muted-foreground">前端地址</span>
            <span className="font-mono">http://localhost:5173</span>
          </div>
          <div className="flex justify-between text-xs py-1">
            <span className="text-muted-foreground">后端地址</span>
            <span className="font-mono">http://localhost:8000</span>
          </div>
          <div className="flex justify-between text-xs py-1">
            <span className="text-muted-foreground">API 文档</span>
            <span className="font-mono">http://localhost:8000/docs</span>
          </div>
          <div className="flex justify-between text-xs py-1">
            <span className="text-muted-foreground">日志位置</span>
            <span className="font-mono">logs/</span>
          </div>
        </div>
      </Card>
    </div>
  );
}