import FormGroup from '../FormGroup';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import type { SkillDraft, WorkflowStep as WorkflowStepType } from '../../types';

interface Props {
  draft: SkillDraft;
  onUpdateWorkflow: (updates: Partial<SkillDraft['workflow']>) => void;
}

function StepEditor({ step, index, onUpdate, onRemove }: {
  step: WorkflowStepType;
  index: number;
  onUpdate: (updates: Partial<WorkflowStepType>) => void;
  onRemove: () => void;
}) {
  return (
    <div className="flex items-start gap-2 p-3 px-4 rounded-[var(--radius-md)] border border-white/6 bg-surface mb-2 transition-colors hover:border-white/12">
      <span className="cursor-grab text-text-tertiary text-[var(--text-md)] p-0.5 opacity-40 select-none">⠿</span>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[var(--text-sm)] text-accent font-mono whitespace-nowrap">
            步骤 {index + 1}
          </span>
          <span className="text-text-tertiary">—</span>
          <Input
            value={step.purpose}
            onChange={(e) => onUpdate({ purpose: e.target.value })}
            placeholder="步骤目的"
            className="text-[var(--text-sm)]"
          />
        </div>
        <div className="grid grid-cols-2 gap-2">
          <Input
            value={step.action}
            onChange={(e) => onUpdate({ action: e.target.value })}
            placeholder="Agent 做什么"
            className="text-[var(--text-sm)]"
          />
          <Input
            value={step.input}
            onChange={(e) => onUpdate({ input: e.target.value })}
            placeholder="需要什么输入"
            className="text-[var(--text-sm)]"
          />
          <Input
            value={step.output}
            onChange={(e) => onUpdate({ output: e.target.value })}
            placeholder="产出什么"
            className="text-[var(--text-sm)]"
          />
          <Input
            value={step.validation}
            onChange={(e) => onUpdate({ validation: e.target.value })}
            placeholder="如何验证"
            className="text-[var(--text-sm)]"
          />
        </div>
      </div>
      <div className="flex gap-1.5 shrink-0">
        <button
          className="appearance-none border-0 bg-none text-text-tertiary cursor-pointer text-[var(--text-md)] p-0.5 transition-colors hover:text-error"
          onClick={onRemove}
          type="button"
          title="删除步骤"
        >
          ✕
        </button>
      </div>
    </div>
  );
}

export default function WorkflowStep({ draft, onUpdateWorkflow }: Props) {
  const w = draft.workflow;

  const addStep = () => {
    const newStep: WorkflowStepType = {
      id: `step_${Date.now()}`,
      purpose: '',
      action: '',
      input: '',
      output: '',
      validation: '',
      failureHandling: '',
    };
    onUpdateWorkflow({ steps: [...w.steps, newStep] });
  };

  const updateStep = (index: number, updates: Partial<WorkflowStepType>) => {
    const steps = [...w.steps];
    steps[index] = { ...steps[index], ...updates };
    onUpdateWorkflow({ steps });
  };

  const removeStep = (index: number) => {
    onUpdateWorkflow({ steps: w.steps.filter((_, i) => i !== index) });
  };

  return (
    <div>
      <FormGroup label="工作流目标" required hint="这个 Skill 要实现什么最终目标">
        <Textarea
          value={w.objective}
          onChange={(e) => onUpdateWorkflow({ objective: e.target.value })}
          placeholder="系统化地完成产品调研，输出结构化报告"
          rows={2}
        />
      </FormGroup>

      <FormGroup label="前置条件" hint="开始之前需要满足什么条件">
        <Input
          value={w.preconditions}
          onChange={(e) => onUpdateWorkflow({ preconditions: e.target.value })}
          placeholder="用户需要提供产品领域关键词"
        />
      </FormGroup>

      <div className="flex justify-between items-center mb-3">
        <p className="text-[var(--text-xs)] tracking-widest uppercase text-muted-foreground m-0 mb-2">工作流步骤</p>
        <Button variant="outline" size="sm" onClick={addStep} type="button">+ 添加步骤</Button>
      </div>

      {w.steps.length === 0 && (
        <div className="py-10 px-5 text-center rounded-[var(--radius-md)] border border-dashed border-white/10 text-muted-foreground">
          还没有步骤，点击「添加步骤」开始定义工作流
        </div>
      )}

      {w.steps.map((step, i) => (
        <StepEditor
          key={step.id}
          step={step}
          index={i}
          onUpdate={(updates) => updateStep(i, updates)}
          onRemove={() => removeStep(i)}
        />
      ))}
    </div>
  );
}