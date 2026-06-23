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
            'rounded-full px-3.5 py-1.5 text-xs border transition-all duration-200 cursor-pointer whitespace-nowrap active:scale-[0.96]',
            selected.includes(opt.value)
              ? 'bg-accent-dim border-accent-border text-accent shadow-[0_0_16px_rgba(14,124,115,0.18)]'
              : 'bg-surface border-black/12 text-muted-foreground hover:border-black/24 hover:bg-black/6 hover:text-foreground hover:-translate-y-px'
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
