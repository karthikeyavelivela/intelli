import { animate, motion, useInView, useMotionValue, useTransform } from "framer-motion";
import { AlertTriangle, ArrowDown, ArrowUp, ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { SafeImage } from "./SafeImage";
import { Button } from "./ui/button";
import { Skeleton } from "./ui/misc";
import type { Img } from "@/config/images";
import { cn, formatValue } from "@/lib/utils";

export function Logo({ className, tone = "auto" }: { className?: string; tone?: "auto" }) {
  return (
    <span className={cn("inline-flex items-center gap-2 font-semibold tracking-tight", className)}>
      <svg viewBox="0 0 32 32" className="h-7 w-7" aria-hidden>
        <rect width="32" height="32" rx="8" className="fill-primary" />
        <path d="M8 22V10l8 8 8-8v12" fill="none" className="stroke-primary-foreground" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="24" cy="9" r="2.4" className="fill-accent" />
      </svg>
      <span>IntelliMetrics <span className="text-muted-foreground">AI</span></span>
    </span>
  );
}

/** Animated counter that formats with the metric unit and respects reduced motion. */
export function AnimatedNumber({ value, unit, decimals }: { value: number | null | undefined; unit?: string | null; decimals?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true });
  const mv = useMotionValue(0);
  const text = useTransform(mv, (v) => (decimals !== undefined ? v.toFixed(decimals) : formatValue(v, unit)));
  useEffect(() => {
    if (value === null || value === undefined || !inView) return;
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reduce) { mv.set(value); return; }
    const c = animate(mv, value, { duration: 0.9, ease: "easeOut" });
    return () => c.stop();
  }, [value, inView, mv]);
  if (value === null || value === undefined) return <span>—</span>;
  return <motion.span ref={ref}>{text}</motion.span>;
}

export function PageHeader({ title, description, actions, eyebrow }: { title: ReactNode; description?: ReactNode; actions?: ReactNode; eyebrow?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
        {description && <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground sm:text-base">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function EmptyState({ title, description, image, action, icon }: { title: string; description?: string; image?: Img; action?: ReactNode; icon?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center overflow-hidden text-center">
      {image && <SafeImage image={image} className="h-36 w-full sm:h-44" />}
      <div className="flex flex-col items-center p-8">
        {icon && <div className="mb-3 rounded-2xl border bg-muted p-3">{icon}</div>}
        <h3 className="text-lg font-semibold">{title}</h3>
        {description && <p className="mt-1.5 max-w-md text-sm text-muted-foreground">{description}</p>}
        {action && <div className="mt-4">{action}</div>}
      </div>
    </div>
  );
}

export function ErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const msg = (error as any)?.message || "Something went wrong";
  return (
    <div role="alert" className="card flex items-start gap-3 border-danger/30 p-5">
      <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-danger" aria-hidden />
      <div className="min-w-0 flex-1">
        <p className="font-medium">Could not load this data</p>
        <p className="mt-0.5 break-words text-sm text-muted-foreground">{msg}</p>
        {(error as any)?.requestId && <p className="mt-1 font-mono text-xs text-muted-foreground">request {(error as any).requestId}</p>}
      </div>
      {retry && <Button size="sm" variant="outline" onClick={retry}>Retry</Button>}
    </div>
  );
}

export function TableSkeleton({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div className="space-y-2 p-4" aria-busy>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4">{Array.from({ length: cols }).map((__, j) => <Skeleton key={j} className="h-6 flex-1" />)}</div>
      ))}
    </div>
  );
}

export interface Column<T> { key: string; header: ReactNode; cell: (row: T) => ReactNode; className?: string; sortKey?: string }
export function DataTable<T>({ columns, rows, rowKey, onRowClick, empty, sort, onSort, dense }: {
  columns: Column<T>[]; rows: T[]; rowKey: (r: T) => string; onRowClick?: (r: T) => void; empty?: ReactNode;
  sort?: string; onSort?: (s: string) => void; dense?: boolean;
}) {
  if (!rows.length && empty) return <>{empty}</>;
  return (
    <div className="w-full overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
            {columns.map((c) => {
              const active = !!sort && !!c.sortKey && sort.replace("-", "") === c.sortKey;
              return (
                <th key={c.key} className={cn("whitespace-nowrap px-4 py-3 font-medium", c.className)} aria-sort={active ? (sort!.startsWith("-") ? "descending" : "ascending") : undefined}>
                  {c.sortKey && onSort ? (
                    <button className="inline-flex items-center gap-1 uppercase tracking-wider hover:text-foreground" onClick={() => onSort(active && !sort!.startsWith("-") ? `-${c.sortKey}` : c.sortKey!)}>
                      {c.header}{active && (sort!.startsWith("-") ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />)}
                    </button>
                  ) : c.header}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={rowKey(r)} onClick={onRowClick && (() => onRowClick(r))} onKeyDown={onRowClick && ((e) => e.key === "Enter" && onRowClick(r))} tabIndex={onRowClick ? 0 : undefined}
              className={cn("border-b last:border-0 transition-colors", onRowClick && "cursor-pointer hover:bg-muted/60 focus-visible:bg-muted/60")}>
              {columns.map((c) => <td key={c.key} className={cn("px-4 align-middle", dense ? "py-2" : "py-3.5", c.className)}>{c.cell(r)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Pager({ page, pageSize, total, onPage }: { page: number; pageSize: number; total: number; onPage: (p: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total <= pageSize) return null;
  return (
    <div className="flex items-center justify-between border-t px-4 py-3 text-sm text-muted-foreground">
      <span>{(page - 1) * pageSize + 1}–{Math.min(total, page * pageSize)} of {total.toLocaleString()}</span>
      <div className="flex items-center gap-1">
        <Button size="icon" variant="ghost" aria-label="Previous page" disabled={page <= 1} onClick={() => onPage(page - 1)}><ChevronLeft className="h-4 w-4" /></Button>
        <span className="px-2 tabular-nums">{page} / {pages}</span>
        <Button size="icon" variant="ghost" aria-label="Next page" disabled={page >= pages} onClick={() => onPage(page + 1)}><ChevronRight className="h-4 w-4" /></Button>
      </div>
    </div>
  );
}

export function useDebounced<T>(value: T, delay = 300): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), delay); return () => clearTimeout(t); }, [value, delay]);
  return v;
}

/** Side-by-side token diff renderer for formulas (server returns {op,a,b} segments). */
export function FormulaDiff({ segments, side }: { segments: { op: string; a: string; b: string }[]; side: "a" | "b" }) {
  return (
    <pre className="whitespace-pre-wrap break-words rounded-xl border bg-muted/50 p-4 font-mono text-sm leading-relaxed" aria-label={`Formula ${side === "a" ? "A" : "B"}`}>
      {segments.map((s, i) => {
        const text = side === "a" ? s.a : s.b;
        if (!text) return null;
        if (s.op === "equal") return <span key={i}>{text}</span>;
        return <mark key={i} className={cn("rounded px-0.5", side === "a" ? "bg-danger/15 text-danger line-through decoration-danger/40" : "bg-success/15 text-success")}>{text}</mark>;
      })}
    </pre>
  );
}

export function CodeBlock({ children, className }: { children: ReactNode; className?: string }) {
  return <pre className={cn("overflow-x-auto rounded-xl border bg-muted/50 p-4 font-mono text-xs leading-relaxed", className)}>{children}</pre>;
}

export function DemoBadge() {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-accent/30 bg-accent/10 px-2.5 py-0.5 text-xs font-medium text-accent" title="Seeded demonstration data">
      <span className="h-1.5 w-1.5 rounded-full bg-accent" /> Demonstration data (synthetic)
    </span>
  );
}

export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link to={to} className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ChevronLeft className="h-4 w-4" />{children}</Link>;
}
