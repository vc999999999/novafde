import FormGroup from '../FormGroup';
import Toggle from '../Toggle';
import { FREEDOM_LEVELS, VALIDATION_LEVELS } from '../../data';
import { cn } from '@/lib/utils';
import type { SkillDraft } from '../../types';

interface Props {
  draft: SkillDraft;
  onUpdateOutputControl: (updates: Partial<SkillDraft['outputControl']>) => void;
}

export default function OutputStep({ draft, onUpdateOutputControl }: Props) {
  const oc = draft.outputControl;

  return (
    <div>
      <FormGroup label="自由度" hint="控制 Agent 在执行中的灵活程度">
        <div className="flex flex-wrap gap-2">
          {FREEDOM_LEVELS.map((level) => (
            <button
              key={level.value}
              className={cn(
                'rounded-full py-1.5 px-3.5 text-[var(--text-sm)] border transition-all cursor-pointer whitespace-nowrap',
                oc.freedom === level.value
                  ? 'bg-accent-dim border-accent-border text-accent'
                  : 'bg-surface border-white/12 text-muted-foreground hover:bg-white/6 hover:text-foreground'
              )}
              onClick={() => onUpdateOutputControl({ freedom: level.value })}
              type="button"
            >
              {level.label}
            </button>
          ))}
        </div>
        <p className="text-[var(--text-sm)] text-muted-foreground mt-1">
          {FREEDOM_LEVELS.find((l) => l.value === oc.freedom)?.desc}
        </p>
      </FormGroup>

      <FormGroup label="校验严格度" hint="控制质量校验的等级">
        <div className="flex flex-wrap gap-2">
          {VALIDATION_LEVELS.map((level) => (
            <button
              key={level.value}
              className={cn(
                'rounded-full py-1.5 px-3.5 text-[var(--text-sm)] border transition-all cursor-pointer whitespace-nowrap',
                oc.validationStrictness === level.value
                  ? 'bg-accent-dim border-accent-border text-accent'
                  : 'bg-surface border-white/12 text-muted-foreground hover:bg-white/6 hover:text-foreground'
              )}
              onClick={() => onUpdateOutputControl({ validationStrictness: level.value })}
              type="button"
            >
              {level.label}
            </button>
          ))}
        </div>
        <p className="text-[var(--text-sm)] text-muted-foreground mt-1">
          {VALIDATION_LEVELS.find((l) => l.value === oc.validationStrictness)?.desc}
        </p>
      </FormGroup>

      <div className="flex flex-col gap-4 mt-2">
        <Toggle label="允许硬性限制" checked={oc.allowHardLimits} onChange={(checked) => onUpdateOutputControl({ allowHardLimits: checked })} />
        <Toggle label="生成安装说明" checked={oc.generateInstallGuide} onChange={(checked) => onUpdateOutputControl({ generateInstallGuide: checked })} />
        <Toggle label="允许带 warning 下载" checked={oc.allowDownloadWithWarnings} onChange={(checked) => onUpdateOutputControl({ allowDownloadWithWarnings: checked })} />
      </div>
    </div>
  );
}