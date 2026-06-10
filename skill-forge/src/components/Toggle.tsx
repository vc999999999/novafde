import { Switch } from '@/components/ui/switch'
import { Label } from '@/components/ui/label'

interface Props {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export default function Toggle({ label, checked, onChange }: Props) {
  return (
    <div className="flex items-center justify-between gap-3">
      <Label className="text-sm text-foreground">{label}</Label>
      <Switch checked={checked} onCheckedChange={onChange} />
    </div>
  );
}