import FormGroup from '../FormGroup';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Button } from '@/components/ui/button';
import ChipList from '../ChipList';
import type { SkillDraft, KnowledgePitfall } from '../../types';

interface Props {
  draft: SkillDraft;
  onUpdateKnowledge: (updates: Partial<SkillDraft['knowledge']>) => void;
}

function PitfallEditor({ pitfall, onUpdate, onRemove }: {
  pitfall: KnowledgePitfall;
  onUpdate: (updates: Partial<KnowledgePitfall>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex flex-col items-stretch gap-0 p-3 px-4 rounded-[var(--radius-md)] border border-white/6 bg-surface mb-2 transition-colors hover:border-white/12">
      <div className="flex justify-between items-center mb-2">
        <span className="text-[var(--text-sm)] text-accent font-mono">易错点</span>
        <button
          className="appearance-none border-0 bg-none text-text-tertiary cursor-pointer transition-colors hover:text-error"
          onClick={onRemove}
          type="button"
        >
          ✕
        </button>
      </div>
      <Input
        value={pitfall.description}
        onChange={(e) => onUpdate({ description: e.target.value })}
        placeholder="易错点描述"
        className="text-[var(--text-sm)] mb-2"
      />
      <div className="grid grid-cols-2 gap-2">
        <Input
          value={pitfall.goodExample}
          onChange={(e) => onUpdate({ goodExample: e.target.value })}
          placeholder="正例"
          className="text-[var(--text-sm)]"
        />
        <Input
          value={pitfall.badExample}
          onChange={(e) => onUpdate({ badExample: e.target.value })}
          placeholder="反例"
          className="text-[var(--text-sm)]"
        />
      </div>
    </div>
  );
}

export default function KnowledgeStep({ draft, onUpdateKnowledge }: Props) {
  const k = draft.knowledge;

  const addPitfall = () => {
    onUpdateKnowledge({
      pitfalls: [...k.pitfalls, { id: `pf_${Date.now()}`, description: '', goodExample: '', badExample: '' }],
    });
  };

  const updatePitfall = (index: number, updates: Partial<KnowledgePitfall>) => {
    const pitfalls = [...k.pitfalls];
    pitfalls[index] = { ...pitfalls[index], ...updates };
    onUpdateKnowledge({ pitfalls });
  };

  const removePitfall = (index: number) => {
    onUpdateKnowledge({ pitfalls: k.pitfalls.filter((_, i) => i !== index) });
  };

  return (
    <div>
      <FormGroup label="行业规则" hint="Agent 不知道但很重要的行业或领域规则">
        <ChipList
          items={k.industryRules}
          onAdd={(v) => onUpdateKnowledge({ industryRules: [...k.industryRules, v] })}
          onRemove={(i) => onUpdateKnowledge({ industryRules: k.industryRules.filter((_, idx) => idx !== i) })}
          placeholder="输入规则后按回车，如：金融数据需标注来源"
        />
      </FormGroup>

      <FormGroup label="内部流程" hint="你团队内部的流程和约定">
        <ChipList
          items={k.internalProcesses}
          onAdd={(v) => onUpdateKnowledge({ internalProcesses: [...k.internalProcesses, v] })}
          onRemove={(i) => onUpdateKnowledge({ internalProcesses: k.internalProcesses.filter((_, idx) => idx !== i) })}
          placeholder="输入流程后按回车"
        />
      </FormGroup>

      <FormGroup label="个人经验" hint="你在实践中总结的关键经验">
        <Textarea
          value={k.personalExperience.join('\n')}
          onChange={(e) => onUpdateKnowledge({ personalExperience: e.target.value.split('\n').filter(Boolean) })}
          placeholder="每行写一条经验"
          rows={3}
        />
      </FormGroup>

      <div className="flex justify-between items-center mb-3">
        <p className="text-[var(--text-xs)] tracking-widest uppercase text-muted-foreground m-0 mb-2">易错点</p>
        <Button variant="outline" size="sm" onClick={addPitfall} type="button">+ 添加易错点</Button>
      </div>

      {k.pitfalls.length === 0 && (
        <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">
          添加易错点，帮助 Agent 避免常见错误
        </div>
      )}

      {k.pitfalls.map((pitfall, i) => (
        <PitfallEditor
          key={pitfall.id}
          pitfall={pitfall}
          onUpdate={(updates) => updatePitfall(i, updates)}
          onRemove={() => removePitfall(i)}
        />
      ))}
    </div>
  );
}