import { Loader2 } from "lucide-react";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

export const Skeleton = ({ className, ...p }: HTMLAttributes<HTMLDivElement>) => <div className={cn("skeleton h-4 w-full", className)} aria-hidden {...p} />;
export const Spinner = ({ className }: { className?: string }) => <Loader2 className={cn("h-4 w-4 animate-spin", className)} aria-label="Loading" />;

export function Progress({ value, className, label }: { value: number; className?: string; label?: string }) {
  const v = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("h-2 w-full overflow-hidden rounded-full bg-muted", className)} role="progressbar" aria-valuenow={v} aria-valuemin={0} aria-valuemax={100} aria-label={label || "Progress"}>
      <div className="h-full rounded-full bg-accent transition-all duration-500" style={{ width: `${v}%` }} />
    </div>
  );
}

export const Kbd = ({ children }: { children: React.ReactNode }) => <kbd className="rounded-md border bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">{children}</kbd>;
