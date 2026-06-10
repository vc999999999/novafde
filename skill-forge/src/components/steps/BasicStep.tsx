import FormGroup from '../FormGroup';
import { Input } from '@/components/ui/input';
import ChipSelect from '../ChipSelect';
import { PLATFORMS } from '../../data';
import type { SkillDraft } from '../../types';

interface Props {
  draft: SkillDraft;
  onUpdate: (updates: Partial<SkillDraft>) => void;
}

function slugify(value: string) {
  const result = value
    .normalize('NFKD')
    .replace(/[^\w\s-]/g, '')
    .trim()
    .toLowerCase()
    .replace(/[\s_]+/g, '-')
    .replace(/-+/g, '-')
    .replace(/^-|-$/g, '');
  return result || 'untitled';
}

export default function BasicStep({ draft, onUpdate }: Props) {
  return (
    <div>
      <FormGroup label="Skill 显示名称" required hint="用户看到的名字，如 Product Research">
        <Input
          value={draft.displayName}
          onChange={(e) => {
            const displayName = e.target.value;
            onUpdate({ displayName, name: draft.name || slugify(displayName) });
          }}
          placeholder="输入 Skill 显示名称"
        />
      </FormGroup>

      <FormGroup label="目标平台" required hint="选择这个 Skill 需要支持的平台">
        <ChipSelect
          options={PLATFORMS.map((p) => ({ value: p.value, label: p.label }))}
          selected={draft.targetPlatforms}
          onChange={(selected) => onUpdate({ targetPlatforms: selected as SkillDraft['targetPlatforms'] })}
        />
      </FormGroup>
    </div>
  );
}
