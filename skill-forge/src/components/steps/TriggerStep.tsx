import FormGroup from '../FormGroup';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import ChipList from '../ChipList';
import type { SkillDraft } from '../../types';

interface Props {
  draft: SkillDraft;
  onUpdateTrigger: (updates: Partial<SkillDraft['trigger']>) => void;
}

export default function TriggerStep({ draft, onUpdateTrigger }: Props) {
  const t = draft.trigger;

  return (
    <div>
      <FormGroup label="用户意图" required hint="用户使用这个 Skill 时想要达成什么目的">
        <Textarea
          value={t.intent}
          onChange={(e) => onUpdateTrigger({ intent: e.target.value })}
          placeholder="例如：帮助用户系统化地完成产品调研"
          rows={2}
        />
      </FormGroup>

      <FormGroup label="任务类型" required hint="这个 Skill 处理什么类型的任务">
        <Input
          value={t.taskType}
          onChange={(e) => onUpdateTrigger({ taskType: e.target.value })}
          placeholder="研究、分析、整理"
        />
      </FormGroup>

      <FormGroup label="正向触发场景" hint="什么情况下应该触发这个 Skill">
        <ChipList
          items={t.positiveExamples}
          onAdd={(v) => onUpdateTrigger({ positiveExamples: [...t.positiveExamples, v] })}
          onRemove={(i) => onUpdateTrigger({ positiveExamples: t.positiveExamples.filter((_, idx) => idx !== i) })}
          placeholder="输入场景后按回车，如：新产品立项"
        />
      </FormGroup>

      <FormGroup label="反向触发场景" hint="什么情况下不应该触发">
        <ChipList
          items={t.negativeExamples}
          onAdd={(v) => onUpdateTrigger({ negativeExamples: [...t.negativeExamples, v] })}
          onRemove={(i) => onUpdateTrigger({ negativeExamples: t.negativeExamples.filter((_, idx) => idx !== i) })}
          placeholder="输入场景后按回车，如：纯技术实现"
        />
      </FormGroup>

      <FormGroup label="用户常见说法" hint="用户会怎么说来触发这个 Skill">
        <ChipList
          items={t.commonPhrases}
          onAdd={(v) => onUpdateTrigger({ commonPhrases: [...t.commonPhrases, v] })}
          onRemove={(i) => onUpdateTrigger({ commonPhrases: t.commonPhrases.filter((_, idx) => idx !== i) })}
          placeholder="输入说法后按回车，如：帮我做个竞品分析"
        />
      </FormGroup>

      <FormGroup label="相关文件类型" hint="与这个 Skill 相关的文件扩展名">
        <ChipList
          items={t.relatedFileTypes}
          onAdd={(v) => onUpdateTrigger({ relatedFileTypes: [...t.relatedFileTypes, v] })}
          onRemove={(i) => onUpdateTrigger({ relatedFileTypes: t.relatedFileTypes.filter((_, idx) => idx !== i) })}
          placeholder="输入文件类型，如：.md, .json"
        />
      </FormGroup>

      <FormGroup label="相关工具" hint="Skill 执行过程中会用到什么工具">
        <ChipList
          items={t.relatedTools}
          onAdd={(v) => onUpdateTrigger({ relatedTools: [...t.relatedTools, v] })}
          onRemove={(i) => onUpdateTrigger({ relatedTools: t.relatedTools.filter((_, idx) => idx !== i) })}
          placeholder="输入工具名后按回车，如：web browser"
        />
      </FormGroup>

      {t.intent && t.intent.length < 10 && (
        <Alert className="border-warning-border bg-warning-dim text-warning">
          <AlertDescription>
            触发意图描述太简短，建议写得更具体以避免误触发
          </AlertDescription>
        </Alert>
      )}
    </div>
  );
}