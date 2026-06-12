import { ChevronDown, Plus, Trash2 } from 'lucide-react';
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

      <details className="group rounded-lg border border-panel-border bg-surface/45">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-medium marker:content-none">
          <span>
            可选质量增强
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              留空时由 Agent 自动补全
            </span>
          </span>
          <ChevronDown className="size-4 text-muted-foreground transition-transform group-open:rotate-180" />
        </summary>

        <div className="border-t border-panel-border px-4 pt-4">
          <FormGroup label="大致执行流程（可选）" hint="提供主要阶段可让结果更贴近你的习惯；不填时由 Agent 设计标准流程">
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

          <FormGroup label="完成标准（可选）" hint="不填时由 Agent 根据目标推导可验证的验收标准">
            <Textarea
              value={purpose.completionCriteria}
              onChange={(event) => onUpdatePurpose({ completionCriteria: event.target.value })}
              placeholder="例如：每个结论都有来源，无法验证的内容明确标记为假设"
              rows={3}
            />
          </FormGroup>

          <FormGroup label="特殊情况（可选）" hint="不填时由 Agent 补全信息不足、异常和失败分支">
            <Textarea
              value={purpose.specialCases}
              onChange={(event) => onUpdatePurpose({ specialCases: event.target.value })}
              placeholder="例如：来源不足时输出缺口清单，不编造结论"
              rows={3}
            />
          </FormGroup>
        </div>
      </details>
    </div>
  );
}
