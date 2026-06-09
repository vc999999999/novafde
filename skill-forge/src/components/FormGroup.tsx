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
      <Label className={cn('text-[var(--text-sm)] text-secondary-foreground tracking-wide', required && 'after:content-["*"] after:text-error after:ml-0.5')}>
        {label}
      </Label>
      {children}
      {hint && !error && <p className="text-[var(--text-sm)] text-muted-foreground mt-1 leading-snug">{hint}</p>}
      {error && <p className="text-[var(--text-sm)] text-destructive mt-1">{error}</p>}
    </div>
  );
}