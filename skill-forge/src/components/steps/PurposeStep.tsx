import { Plus, Trash2 } from 'lucide-react';
import FormGroup from '../FormGroup';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import type { SkillDraft } from '../../types';

interface Props {
  draft: SkillDraft;
  onUpdatePurpose: (updates: Partial<SkillDraft['purpose']>) => void;
}

export default function PurposeStep({ draft, onUpdatePurpose }: Props) {
  const purpose = draft.purpose;

  const updateProcessItem = (index: number, value: string) => {
    const process = [...purpose.process];
    process[index] = value;
    onUpdatePurpose({ process });
  };

  return (
    <div>
      <FormGroup label="什么时候使用" required hint="描述用户在什么任务或意图下需要这个 Skill">
        <Textarea
          value={purpose.usage}
          onChange={(event) => onUpdatePurpose({ usage: event.target.value })}
          placeholder="例如：当产品团队需要系统化完成竞品调研时使用"
          rows={3}
        />
      </FormGroup>

      <FormGroup label="希望得到什么结果" required hint="写清楚最终产物或状态">
        <Textarea
          value={purpose.desiredOutcome}
          onChange={(event) => onUpdatePurpose({ desiredOutcome: event.target.value })}
          placeholder="例如：把零散市场信息转成可验证的产品研究结论"
          rows={3}
        />
      </FormGroup>

      <FormGroup label="大致怎么做" required hint="只写主要阶段，详细输入、输出和校验由 Skill Creator 决定">
        <div className="flex flex-col gap-2">
          {purpose.process.map((item, index) => (
            <div className="flex items-center gap-2" key={`process-${index}`}>
              <span className="w-6 shrink-0 text-center font-mono text-xs text-accent">{index + 1}</span>
              <Input
                value={item}
                onChange={(event) => updateProcessItem(index, event.target.value)}
                placeholder="例如：明确研究范围和关键问题"
              />
              <Button
                aria-label={`删除第 ${index + 1} 个流程阶段`}
                size="icon"
                title="删除流程阶段"
                type="button"
                variant="outline"
                onClick={() => onUpdatePurpose({
                  process: purpose.process.filter((_, itemIndex) => itemIndex !== index),
                })}
              >
                <Trash2 className="size-4" />
              </Button>
            </div>
          ))}
          <Button
            className="self-start"
            type="button"
            variant="outline"
            onClick={() => onUpdatePurpose({ process: [...purpose.process, ''] })}
          >
            <Plus className="size-4" />
            添加阶段
          </Button>
        </div>
      </FormGroup>

      <FormGroup label="怎样算完成" hint="可选；不填时由 Skill Creator 推导，评测发现缺口会在生成中向你确认">
        <Textarea
          value={purpose.completionCriteria}
          onChange={(event) => onUpdatePurpose({ completionCriteria: event.target.value })}
          placeholder="例如：每个结论都有来源，无法验证的内容明确标记为假设"
          rows={3}
        />
      </FormGroup>

      <FormGroup label="特殊情况如何处理" hint="可选；说明异常、信息不足或特殊分支">
        <Textarea
          value={purpose.specialCases}
          onChange={(event) => onUpdatePurpose({ specialCases: event.target.value })}
          placeholder="例如：来源不足时输出缺口清单，不编造结论"
          rows={3}
        />
      </FormGroup>
    </div>
  );
}
