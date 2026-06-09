import FormGroup from '../FormGroup';
import { Input } from '@/components/ui/input';
import ChipSelect from '../ChipSelect';
import { PLATFORMS, SKILL_TYPES } from '../../data';
import type { SkillDraft } from '../../types';

const selectClasses = "appearance-none w-full p-2.5 px-3.5 rounded-[var(--radius-md)] border border-white/10 bg-surface text-foreground font-inherit text-[var(--text-base)] cursor-pointer transition-colors focus:outline-none focus:border-accent focus:bg-white/5";
const selectStyle = { backgroundImage: "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='rgba(255,255,255,0.6)' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E\")", backgroundRepeat: 'no-repeat', backgroundPosition: 'right 12px center', paddingRight: '36px' } as React.CSSProperties;

interface Props {
  draft: SkillDraft;
  onUpdate: (updates: Partial<SkillDraft>) => void;
}

export default function BasicStep({ draft, onUpdate }: Props) {
  return (
    <div>
      <FormGroup label="Skill 显示名称" required hint="用户看到的名字，如 Product Research">
        <Input
          value={draft.displayName}
          onChange={(e) => onUpdate({ displayName: e.target.value })}
          placeholder="输入 Skill 显示名称"
        />
      </FormGroup>

      <FormGroup label="Skill 文件夹名称" required hint="用于文件系统，仅限小写字母、数字和连字符">
        <Input
          value={draft.name}
          onChange={(e) => onUpdate({ name: e.target.value.replace(/[^a-z0-9-]/g, '-') })}
          placeholder="product-research"
        />
      </FormGroup>

      <FormGroup label="输出语言">
        <select
          className={selectClasses}
          style={selectStyle}
          value={draft.language}
          onChange={(e) => onUpdate({ language: e.target.value as SkillDraft['language'] })}
        >
          <option value="zh-CN">中文 (zh-CN)</option>
          <option value="en">English (en)</option>
        </select>
      </FormGroup>

      <FormGroup label="Skill 类型">
        <select
          className={selectClasses}
          style={selectStyle}
          value={draft.skillType}
          onChange={(e) => onUpdate({ skillType: e.target.value as SkillDraft['skillType'] })}
        >
          {SKILL_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>
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