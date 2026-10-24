import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const badge = cva("inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap", {
  variants: {
    tone: {
      neutral: "bg-muted text-foreground",
      outline: "bg-transparent text-muted-foreground",
      accent: "border-accent/30 bg-accent/10 text-accent",
      success: "border-success/30 bg-success/10 text-success",
      warning: "border-warning/30 bg-warning/10 text-warning",
      danger: "border-danger/30 bg-danger/10 text-danger",
      solid: "border-transparent bg-primary text-primary-foreground",
    },
  },
  defaultVariants: { tone: "neutral" },
});
export const Badge = ({ className, tone, ...p }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badge>) => <span className={cn(badge({ tone }), className)} {...p} />;

const STATUS: Record<string, "neutral" | "accent" | "success" | "warning" | "danger" | "outline"> = {
  draft: "neutral", in_review: "warning", approved: "accent", published: "success", deprecated: "outline",
  ready: "success", processing: "accent", pending: "warning", failed: "danger", queued: "warning", running: "accent", succeeded: "success",
  open: "danger", assigned: "warning", resolved: "success", dismissed: "outline", ok: "success",
  low: "neutral", medium: "warning", high: "danger", critical: "danger",
};
export const StatusBadge = ({ status }: { status: string }) => <Badge tone={STATUS[status] || "neutral"} className="capitalize">{status.replace(/_/g, " ")}</Badge>;
