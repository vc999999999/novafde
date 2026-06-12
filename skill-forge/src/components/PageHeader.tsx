import type { ReactNode } from 'react';

interface Props {
  title: string;
  sub?: ReactNode;
  actions?: ReactNode;
}

export default function PageHeader({ title, sub, actions }: Props) {
  return (
    <section className="mb-5 flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 items-baseline gap-3">
        <h1 className="text-lg font-semibold leading-tight">{title}</h1>
        {sub != null && (
          <>
            <span aria-hidden className="text-tertiary">/</span>
            <span className="flex min-w-0 items-baseline gap-3 truncate text-sm text-muted-foreground">{sub}</span>
          </>
        )}
      </div>
      {actions}
    </section>
  );
}
