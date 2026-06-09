import { cn } from '@/lib/utils';

interface Props {
  options: { value: string; label: string }[];
  selected: string[];
  onChange: (selected: string[]) => void;
}

export default function ChipSelect({ options, selected, onChange }: Props) {
  const toggle = (value: string) => {
    if (selected.includes(value)) {
      onChange(selected.filter((v) => v !== value));
    } else {
      onChange([...selected, value]);
    }
  };

  return (
    <div className="flex flex-wrap gap-2">
      {options.map((opt) => (
        <button
          key={opt.value}
          className={cn(
            'rounded-full px-3.5 py-1.5 text-[var(--text-sm)] border transition-all cursor-pointer whitespace-nowrap',
            selected.includes(opt.value)
              ? 'bg-accent-dim border-accent-border text-accent'
              : 'bg-surface border-white/12 text-muted-foreground hover:bg-white/6 hover:text-foreground'
          )}
          onClick={() => toggle(opt.value)}
          type="button"
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}