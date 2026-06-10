import { useCallback, useEffect, useState } from 'react';
import type { ModelConnectionStatus as Connection, Page } from './types';
import CreatePage from './pages/CreatePage';
import HistoryPage from './pages/HistoryPage';
import RulesPage from './pages/RulesPage';
import SettingsPage from './pages/SettingsPage';
import LocalRunPage from './pages/LocalRunPage';
import ModelConnectionStatus from './components/ModelConnectionStatus';
import { getModelConnectionStatus } from './api';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';


const NAV_ITEMS: { key: Page; label: string }[] = [
  { key: 'create', label: '创建' },
  { key: 'history', label: '历史' },
  { key: 'rules', label: '规则' },
  { key: 'settings', label: '设置' },
  { key: 'local', label: '本地运行' },
];

const INITIAL_CONNECTION: Connection = {
  status: 'connecting',
  generationProvider: null,
  judgeProvider: null,
  checkedAt: null,
  message: '正在读取本地模型连接状态。',
};

export default function App() {
  const [page, setPage] = useState<Page>('create');
  const [connection, setConnection] = useState<Connection>(INITIAL_CONNECTION);
  const [generationToOpen, setGenerationToOpen] = useState<string | null>(null);

  const refreshConnection = useCallback(async () => {
    try {
      setConnection(await getModelConnectionStatus());
    } catch (error) {
      setConnection({
        status: 'error',
        generationProvider: null,
        judgeProvider: null,
        checkedAt: null,
        message: error instanceof Error ? error.message : '无法连接本地后端。',
      });
    }
  }, []);

  const openGeneration = useCallback((generationId: string) => {
    setGenerationToOpen(generationId);
    setPage('create');
  }, []);

  useEffect(() => {
    const initialCheck = window.setTimeout(() => void refreshConnection(), 0);
    const interval = window.setInterval(() => void refreshConnection(), 10_000);
    const handleProviderChange = () => void refreshConnection();
    window.addEventListener('skillforge-provider-changed', handleProviderChange);
    return () => {
      window.clearTimeout(initialCheck);
      window.clearInterval(interval);
      window.removeEventListener('skillforge-provider-changed', handleProviderChange);
    };
  }, [refreshConnection]);

  return (
    <div className="mx-auto flex w-full max-w-[1380px] flex-1 flex-col px-5 pb-12 pt-5">
      <div className="mb-4 flex flex-col items-stretch justify-between gap-3 sm:h-12 sm:flex-row sm:items-center">
        <div className="flex min-w-0 items-center gap-3">
          <a
            className="select-none text-sm font-bold tracking-wide text-foreground no-underline"
            href="#"
            onClick={(event) => {
              event.preventDefault();
              setGenerationToOpen(null);
              setPage('create');
            }}
          >
            Nova<span className="text-accent">FDE</span>
          </a>
          <ModelConnectionStatus
            connection={connection}
            onOpenSettings={() => {
              setPage('settings');
              void refreshConnection();
            }}
          />
        </div>

        <Tabs
          value={page}
          onValueChange={(value) => {
            if (value === 'create') setGenerationToOpen(null);
            setPage(value as Page);
          }}
          className="w-full min-w-0 overflow-x-auto sm:w-auto"
        >
          <TabsList className="h-auto w-max min-w-full gap-1 rounded-full border border-panel-border bg-surface px-[3px] py-[3px] sm:min-w-0">
            {NAV_ITEMS.map((item) => (
              <TabsTrigger
                key={item.key}
                value={item.key}
                className="rounded-full px-3.5 py-1.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground data-[state=active]:bg-white/12 data-[state=active]:text-foreground"
              >
                {item.label}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {page === 'create' && (
        <CreatePage
          connection={connection}
          onOpenSettings={() => setPage('settings')}
          resumeGenerationId={generationToOpen}
        />
      )}
      {page === 'history' && (
        <HistoryPage
          connection={connection}
          onOpenGeneration={openGeneration}
          onOpenSettings={() => setPage('settings')}
        />
      )}
      {page === 'rules' && <RulesPage />}
      {page === 'settings' && <SettingsPage />}
      {page === 'local' && <LocalRunPage />}
    </div>
  );
}
