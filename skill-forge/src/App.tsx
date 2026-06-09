import { useState } from 'react';
import type { Page, AppMode } from './types';
import CreatePage from './pages/CreatePage';
import HistoryPage from './pages/HistoryPage';
import RulesPage from './pages/RulesPage';
import SettingsPage from './pages/SettingsPage';
import LocalRunPage from './pages/LocalRunPage';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Monitor, Cloud, Check } from 'lucide-react';

const NAV_ITEMS: { key: Page; label: string }[] = [
  { key: 'create', label: '创建' },
  { key: 'history', label: '历史' },
  { key: 'rules', label: '规则' },
  { key: 'settings', label: '设置' },
  { key: 'local', label: '本地运行' },
];

const MODE_LABELS: Record<AppMode, string> = {
  local: '本地',
  server: '服务器',
};

export default function App() {
  const [page, setPage] = useState<Page>('create');
  const [mode, setMode] = useState<AppMode>(() => {
    // 记住上次选择
    const saved = localStorage.getItem('novafde-mode');
    return (saved === 'local' || saved === 'server') ? saved : 'local';
  });
  const [showModeModal, setShowModeModal] = useState(() => {
    // 首次访问时显示选择弹窗
    return !localStorage.getItem('novafde-mode');
  });

  const handleSelectMode = (selected: AppMode) => {
    setMode(selected);
    localStorage.setItem('novafde-mode', selected);
    setShowModeModal(false);
  };

  const handleSwitchMode = () => {
    setShowModeModal(true);
  };

  return (
    <div className="flex flex-col flex-1 max-w-[1380px] mx-auto px-5 pb-12 pt-5 w-full">
      {/* Mode selection dialog */}
      {showModeModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setShowModeModal(false)}>
          <div className="w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <Card className="bg-gradient-to-b from-white/[0.05] to-white/[0.02] border-panel-border shadow-2xl p-6">
              <div className="text-center mb-6">
                <h2 className="text-[var(--text-xl)] font-semibold text-foreground mb-2">
                  Nova<span className="text-accent">FDE</span>
                </h2>
                <p className="text-[var(--text-sm)] text-muted-foreground leading-[var(--leading-relaxed)]">
                  选择使用方式以继续
                </p>
              </div>

              <div className="flex flex-col gap-3">
                <Card
                  className={`cursor-pointer transition-all duration-200 hover:-translate-y-0.5 border shadow-sm p-5 group ${
                    mode === 'local'
                      ? 'border-accent-border bg-accent-dim'
                      : 'border-panel-border bg-gradient-to-b from-white/[0.035] to-white/[0.01] hover:border-accent-border'
                  }`}
                  onClick={() => handleSelectMode('local')}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-[var(--radius-sm)] bg-accent-dim border border-accent-border flex items-center justify-center shrink-0">
                      <Monitor className="size-5 text-accent" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-[var(--text-md)] font-semibold text-foreground">本地使用</h3>
                      <p className="text-[var(--text-sm)] text-muted-foreground mt-0.5 leading-[var(--leading-relaxed)]">
                        在本地开发机上运行，适合开发和测试
                      </p>
                      <p className="text-[var(--text-xs)] text-tertiary mt-1.5">
                        前端和后端都在本机，通过 localhost 访问
                      </p>
                    </div>
                    {mode === 'local' && (
                      <Check className="size-4 text-accent shrink-0" />
                    )}
                  </div>
                </Card>

                <Card
                  className={`cursor-pointer transition-all duration-200 hover:-translate-y-0.5 border shadow-sm p-5 group ${
                    mode === 'server'
                      ? 'border-accent-border bg-accent-dim'
                      : 'border-panel-border bg-gradient-to-b from-white/[0.035] to-white/[0.01] hover:border-white/20'
                  }`}
                  onClick={() => handleSelectMode('server')}
                >
                  <div className="flex items-start gap-3">
                    <div className="w-9 h-9 rounded-[var(--radius-sm)] bg-surface-up border border-white/12 flex items-center justify-center shrink-0 group-hover:border-accent-border transition-colors">
                      <Cloud className="size-5 text-muted-foreground group-hover:text-accent transition-colors" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <h3 className="text-[var(--text-md)] font-semibold text-foreground">服务器部署</h3>
                      <p className="text-[var(--text-sm)] text-muted-foreground mt-0.5 leading-[var(--leading-relaxed)]">
                        部署到服务器供团队使用，适合生产环境
                      </p>
                      <p className="text-[var(--text-xs)] text-tertiary mt-1.5">
                        前端打包部署，后端作为服务运行，通过域名/IP 访问
                      </p>
                    </div>
                    {mode === 'server' && (
                      <Check className="size-4 text-accent shrink-0" />
                    )}
                  </div>
                </Card>
              </div>

              {localStorage.getItem('novafde-mode') && (
                <div className="mt-5 pt-4 border-t border-panel-border text-center">
                  <Button onClick={() => setShowModeModal(false)} type="button" className="w-full">
                    确认
                  </Button>
                </div>
              )}
            </Card>
          </div>
        </div>
      )}

      {/* Top Nav — always visible */}
      <div className="flex items-center justify-between gap-4 mb-3 h-12">
        <div className="flex items-center gap-3">
          <a className="text-[var(--text-md)] font-bold tracking-wide text-foreground no-underline select-none" href="#" onClick={(e) => { e.preventDefault(); setPage('create'); }}>
            Nova<span className="text-accent">FDE</span>
          </a>
          <Badge
            className="gap-1.5 text-[var(--text-xs)] tracking-widest uppercase cursor-pointer hover:opacity-80 transition-opacity"
            onClick={handleSwitchMode}
            variant="outline"
          >
            <span className={`inline-block size-1.5 rounded-full ${mode === 'server' ? 'bg-accent' : 'bg-success'}`} />
            {MODE_LABELS[mode]}
          </Badge>
        </div>
        <Tabs value={page} onValueChange={(v) => setPage(v as Page)}>
          <TabsList className="rounded-full border border-panel-border bg-surface px-[3px] py-[3px] gap-1 h-auto">
            {NAV_ITEMS.map((item) => (
              <TabsTrigger
                key={item.key}
                value={item.key}
                className="rounded-full px-3.5 py-1.5 text-[13px] data-[state=active]:bg-white/12 data-[state=active]:text-foreground text-muted-foreground hover:text-foreground transition-colors"
              >
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {/* Page Content */}
      {page === 'create' && <CreatePage />}
      {page === 'history' && <HistoryPage />}
      {page === 'rules' && <RulesPage />}
      {page === 'settings' && <SettingsPage onModeChange={setMode} mode={mode} />}
      {page === 'local' && <LocalRunPage />}
    </div>
  );
}