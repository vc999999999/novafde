import { useCallback, useEffect, useState } from 'react';
import {
  createTriggerEvalSet,
  deleteTriggerEvalSet,
  listTriggerEvalSets,
  updateTriggerEvalSet,
} from '../api';
import type { TriggerEvalQuery, TriggerEvalSet } from '../types';
import FormGroup from './FormGroup';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import { Plus, Trash2 } from 'lucide-react';

const EMPTY_QUERY: TriggerEvalQuery = { query: '', shouldTrigger: true };

function messageFromError(error: unknown) {
  return error instanceof Error ? error.message : '操作失败。';
}

function isAutoEvalSet(evalSet: TriggerEvalSet) {
  return evalSet.id.startsWith('auto-');
}

interface Props {
  mode?: 'select' | 'manage';
  selectedId?: string;
  generationId?: string;
  onSelectId?: (id: string) => void;
  className?: string;
}

export default function TriggerEvalSetManager({
  mode = 'select',
  selectedId = 'auto',
  generationId,
  onSelectId,
  className,
}: Props) {
  const [evalSets, setEvalSets] = useState<TriggerEvalSet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(mode === 'manage');
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<TriggerEvalSet | null>(null);
  const [draftName, setDraftName] = useState('');
  const [draftQueries, setDraftQueries] = useState<TriggerEvalQuery[]>([{ ...EMPTY_QUERY }]);
  const [saving, setSaving] = useState(false);

  const loadSets = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setEvalSets(await listTriggerEvalSets());
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSets();
  }, [loadSets]);

  const customSets = evalSets.filter((item) => !isAutoEvalSet(item));
  const generationAutoSet = generationId
    ? evalSets.find((item) => item.id === `auto-${generationId}`)
    : undefined;

  const beginCreate = () => {
    setEditing(null);
    setDraftName('');
    setDraftQueries([
      { query: '', shouldTrigger: true },
      { query: '', shouldTrigger: false },
    ]);
    setFormOpen(true);
    setPanelOpen(true);
  };

  const beginEdit = (evalSet: TriggerEvalSet) => {
    if (isAutoEvalSet(evalSet)) return;
    setEditing(evalSet);
    setDraftName(evalSet.name);
    setDraftQueries(evalSet.queries.map((q) => ({ ...q })));
    setFormOpen(true);
    setPanelOpen(true);
  };

  const saveDraft = async () => {
    const queries = draftQueries
      .map((q) => ({ query: q.query.trim(), shouldTrigger: q.shouldTrigger }))
      .filter((q) => q.query);
    if (!draftName.trim() || queries.length < 2) {
      setError('请填写名称，并至少提供 2 条有效 query。');
      return;
    }
    setSaving(true);
    setError(null);
    try {
      if (editing) {
        await updateTriggerEvalSet(editing.id, { name: draftName.trim(), queries });
      } else {
        const created = await createTriggerEvalSet(draftName.trim(), queries);
        onSelectId?.(created.id);
      }
      setPanelOpen(false);
      setFormOpen(false);
      setEditing(null);
      await loadSets();
    } catch (err) {
      setError(messageFromError(err));
    } finally {
      setSaving(false);
    }
  };

  const removeSet = async (evalSetId: string) => {
    if (!window.confirm('确认删除这个评测集吗？')) return;
    setError(null);
    try {
      await deleteTriggerEvalSet(evalSetId);
      if (selectedId === evalSetId) onSelectId?.('auto');
      await loadSets();
    } catch (err) {
      setError(messageFromError(err));
    }
  };

  const updateQuery = (index: number, patch: Partial<TriggerEvalQuery>) => {
    setDraftQueries((prev) => prev.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  };

  return (
    <div className={cn('flex flex-col gap-3', className)}>
      {mode === 'select' && (
        <FormGroup
          label="触发评测集"
          hint="auto 会从当前草稿自动生成应触发/不应触发的 query；也可选用自定义评测集。"
        >
          <div className="flex flex-wrap items-center gap-2">
            <select
              className="min-w-[220px] flex-1 rounded-[var(--radius-sm)] border border-black/10 bg-surface px-3 py-2 text-sm"
              value={selectedId}
              onChange={(event) => onSelectId?.(event.target.value)}
              disabled={loading}
            >
              <option value="auto">自动（从草稿生成）</option>
              {generationAutoSet && (
                <option value={generationAutoSet.id}>
                  {generationAutoSet.name}（已生成）
                </option>
              )}
              {customSets.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}（{item.queries.length} 条）
                </option>
              ))}
            </select>
            <Button type="button" variant="outline" size="sm" onClick={() => setPanelOpen((v) => !v)}>
              {panelOpen ? '收起管理' : '管理评测集'}
            </Button>
          </div>
        </FormGroup>
      )}

      {error && (
        <Alert className="border-warning-border bg-warning-dim text-warning">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {(mode === 'manage' || panelOpen) && (
        <Card className="border-panel-border bg-panel p-4 shadow-md">
          <div className="mb-3 flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">触发评测集管理</p>
            <Button type="button" size="sm" onClick={beginCreate}>
              <Plus className="size-3.5" />
              新建评测集
            </Button>
          </div>

          {loading ? (
            <p className="text-sm text-muted-foreground">加载中…</p>
          ) : (
            <div className="mb-4 flex flex-col gap-2">
              {evalSets.length === 0 && (
                <p className="text-sm text-muted-foreground">暂无评测集，请新建或在使用时选择 auto。</p>
              )}
              {evalSets.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-sm)] border border-black/6 bg-surface px-3 py-2 text-sm"
                >
                  <div className="min-w-0">
                    <p className="font-medium">{item.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {item.queries.length} 条 query
                      {isAutoEvalSet(item) ? ' · 自动生成' : ''}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {mode === 'select' && onSelectId && (
                      <Button type="button" size="sm" variant="outline" onClick={() => onSelectId(item.id)}>
                        选用
                      </Button>
                    )}
                    {!isAutoEvalSet(item) && (
                      <>
                        <Button type="button" size="sm" variant="outline" onClick={() => beginEdit(item)}>
                          编辑
                        </Button>
                        <Button type="button" size="sm" variant="ghost" onClick={() => void removeSet(item.id)}>
                          <Trash2 className="size-3.5" />
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}

          {formOpen && (
            <div className="rounded-[var(--radius-sm)] border border-black/6 bg-surface p-4">
              <p className="mb-3 text-sm font-medium">{editing ? '编辑评测集' : '新建评测集'}</p>
              <FormGroup label="名称" required>
                <Input
                  value={draftName}
                  onChange={(event) => setDraftName(event.target.value)}
                  placeholder="例如：支付场景触发测试"
                />
              </FormGroup>
              <div className="mb-3 flex flex-col gap-2">
                <p className="text-sm font-medium">Query 列表</p>
                {draftQueries.map((query, index) => (
                  <div key={index} className="grid grid-cols-1 gap-2 md:grid-cols-[minmax(0,1fr)_140px_40px]">
                    <Textarea
                      value={query.query}
                      onChange={(event) => updateQuery(index, { query: event.target.value })}
                      placeholder="用户会输入的 query"
                      rows={2}
                    />
                    <select
                      className="rounded-[var(--radius-sm)] border border-black/10 bg-bg px-3 py-2 text-sm"
                      value={query.shouldTrigger ? 'yes' : 'no'}
                      onChange={(event) => updateQuery(index, { shouldTrigger: event.target.value === 'yes' })}
                    >
                      <option value="yes">应触发</option>
                      <option value="no">不应触发</option>
                    </select>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={draftQueries.length <= 2}
                      onClick={() => setDraftQueries((prev) => prev.filter((_, i) => i !== index))}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>
                ))}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="self-start"
                  onClick={() => setDraftQueries((prev) => [...prev, { ...EMPTY_QUERY }])}
                >
                  <Plus className="size-3.5" />
                  添加 query
                </Button>
              </div>
              <div className="flex gap-2">
                <Button type="button" size="sm" disabled={saving} onClick={() => void saveDraft()}>
                  {saving ? '保存中…' : '保存评测集'}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setFormOpen(false);
                    setEditing(null);
                    setDraftName('');
                    setDraftQueries([{ ...EMPTY_QUERY }]);
                  }}
                >
                  清空表单
                </Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
