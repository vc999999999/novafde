import { Input } from '@/components/ui/input';

interface Props {
  items: string[];
  onAdd: (item: string) => void;
  onRemove: (index: number) => void;
  placeholder?: string;
}

export default function ChipList({ items, onAdd, onRemove, placeholder = '输入后按回车添加' }: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap gap-2">
        {items.map((item, i) => (
          <span key={i} className="inline-flex items-center gap-1.5 bg-accent-dim text-accent border border-accent-border rounded-full py-1.5 px-3.5 text-xs">
            {item}
            <button
              className="text-accent/70 hover:text-accent cursor-pointer text-sm leading-none p-0"
              onClick={() => onRemove(i)}
              type="button"
            >
              ×
            </button>
          </span>
        ))}
      </div>
      <Input
        placeholder={placeholder}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && e.currentTarget.value.trim()) {
            e.preventDefault();
            onAdd(e.currentTarget.value.trim());
            e.currentTarget.value = '';
          }
        }}
      />
    </div>
  );
}