import type { ReactNode } from "react";

interface PanelProps {
  title: string;
  /** Right-aligned slot in the header rail — counts, filters, small inputs. */
  aside?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Panel({ title, aside, children, className = "", bodyClassName = "" }: PanelProps) {
  return (
    <section
      className={`flex min-h-0 min-w-0 flex-col border border-terminal-line bg-terminal-panel ${className}`}
      aria-label={title}
    >
      <header className="flex h-7 shrink-0 items-center justify-between border-b border-terminal-line bg-terminal-raised px-2.5">
        <h2 className="eyebrow flex items-center gap-1.5">
          <span aria-hidden className="h-2 w-[2px] bg-accent" />
          {title}
        </h2>
        {aside}
      </header>
      <div className={`min-h-0 flex-1 ${bodyClassName}`}>{children}</div>
    </section>
  );
}
