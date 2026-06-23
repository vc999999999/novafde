import { Label } from '@/components/ui/label'
import { cn } from '@/lib/utils'

interface Props {
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}

export default function FormGroup({ label, required, hint, error, children }: Props) {
  return (
    <div className="mb-5">
      <Label className={cn(required && 'after:content-["*"] after:text-destructive after:ml-0.5')}>
        {label}
      </Label>
      <div className="mt-1.5">{children}</div>
      {hint && !error && <p className="text-xs text-muted-foreground mt-1.5 leading-snug">{hint}</p>}
      {error && <p className="text-xs text-destructive mt-1.5">{error}</p>}
    </div>
  );
}
