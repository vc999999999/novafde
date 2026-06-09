import FormGroup from '../FormGroup';
import { Textarea } from '@/components/ui/textarea';
import ChipList from '../ChipList';
import Toggle from '../Toggle';
import type { SkillDraft } from '../../types';

interface Props {
  draft: SkillDraft;
  onUpdateContext: (updates: Partial<SkillDraft['context']>) => void;
}

export default function ContextStep({ draft, onUpdateContext }: Props) {
  const c = draft.context;

  return (
    <div>
      <FormGroup label="需要读取的文件或目录" hint="列出 Agent 执行时需要读取的路径">
        <ChipList
          items={c.filesToRead}
          onAdd={(v) => onUpdateContext({ filesToRead: [...c.filesToRead, v] })}
          onRemove={(i) => onUpdateContext({ filesToRead: c.filesToRead.filter((_, idx) => idx !== i) })}
          placeholder="输入路径后按回车，如：src/**/*.ts"
        />
      </FormGroup>

      <div className="flex flex-col gap-4 mt-2 mb-5">
        <Toggle label="需要 references/ 目录" checked={c.needsReferences} onChange={(checked) => onUpdateContext({ needsReferences: checked })} />
        <Toggle label="需要 scripts/ 目录" checked={c.needsScripts} onChange={(checked) => onUpdateContext({ needsScripts: checked })} />
        <Toggle label="需要 assets/ 目录" checked={c.needsAssets} onChange={(checked) => onUpdateContext({ needsAssets: checked })} />
      </div>

      <FormGroup label="上下文加载规则" hint="定义 Agent 如何加载这些文件">
        <Textarea
          value={c.loadingRule}
          onChange={(e) => onUpdateContext({ loadingRule: e.target.value })}
          placeholder="按需加载，优先 references/ 目录下的文件"
          rows={2}
        />
      </FormGroup>
    </div>
  );
}