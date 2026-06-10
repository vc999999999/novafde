import FormGroup from '../FormGroup';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
        <span className="text-xs text-accent font-mono">常见错误或反例</span>
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
        placeholder="错误做法、错误判断或需要避免的结果"
        className="mb-2"
      />
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
        <Input
          value={pitfall.goodExample}
          onChange={(e) => onUpdate({ goodExample: e.target.value })}
          placeholder="正确做法"
        />
        <Input
          value={pitfall.badExample}
          onChange={(e) => onUpdate({ badExample: e.target.value })}
          placeholder="错误示例"
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
      <FormGroup label="Agent 需要知道的专业信息" required hint="领域知识、业务经验、判断依据或内部流程">
        <ChipList
          items={k.professionalInformation}
          onAdd={(value) => onUpdateKnowledge({
            professionalInformation: [...k.professionalInformation, value],
          })}
          onRemove={(index) => onUpdateKnowledge({
            professionalInformation: k.professionalInformation.filter((_, itemIndex) => itemIndex !== index),
          })}
          placeholder="输入一条专业信息后按回车"
        />
      </FormGroup>

      <FormGroup label="必须遵守的规则" required hint="这些规则拥有最高优先级，补充说明和 Agent 都不能覆盖">
        <ChipList
          items={k.mandatoryRules}
          onAdd={(value) => onUpdateKnowledge({ mandatoryRules: [...k.mandatoryRules, value] })}
          onRemove={(index) => onUpdateKnowledge({
            mandatoryRules: k.mandatoryRules.filter((_, itemIndex) => itemIndex !== index),
          })}
          placeholder="输入一条不可违反的规则后按回车"
        />
      </FormGroup>

      <Alert className="mb-5 border-warning-border bg-warning-dim text-warning">
        <AlertDescription>
          必须遵守的规则会原样进入生成结果，并覆盖所有相冲突的补充说明。
        </AlertDescription>
      </Alert>

      <div className="flex justify-between items-center mb-3">
        <p className="text-[11px] tracking-widest uppercase text-muted-foreground m-0 mb-2">常见错误或反例 *</p>
        <Button variant="outline" size="sm" onClick={addPitfall} type="button">添加一项</Button>
      </div>

      {k.pitfalls.length === 0 && (
        <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">
          由你说明常见错误或反例，Skill Creator 不会替你猜测
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

      <FormGroup label="依赖或协同 Skill" hint="可选；填写这个 Skill 会调用、依赖或配合使用的其他 Skill">
        <ChipList
          items={k.relatedSkills}
          onAdd={(value) => onUpdateKnowledge({ relatedSkills: [...k.relatedSkills, value] })}
          onRemove={(index) => onUpdateKnowledge({
            relatedSkills: k.relatedSkills.filter((_, itemIndex) => itemIndex !== index),
          })}
          placeholder="输入 Skill 名称后按回车"
        />
      </FormGroup>
    </div>
  );
}
