import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Info, MessageSquareWarning } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, PageHeader } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { IMAGES } from "@/config/images";
import { api } from "@/lib/api";
import { cn, timeAgo } from "@/lib/utils";

const ICON: Record<string, any> = { success: CheckCircle2, warning: AlertTriangle, error: AlertTriangle, review: MessageSquareWarning, info: Info };

export default function Notifications() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const n = useQuery({ queryKey: ["notifications", "all"], queryFn: () => api.get("/notifications?limit=100") });
  const act = useQuery({ queryKey: ["activity", "full"], queryFn: () => api.get("/activity?limit=60") });
  const open = async (x: any) => { if (!x.read) { await api.post(`/notifications/${x.id}/read`); qc.invalidateQueries({ queryKey: ["notifications"] }); } if (x.link) nav(x.link); };
  return (
    <div>
      <PageHeader title="Activity" description="Notifications addressed to you and a live feed of what is happening in the workspace." actions={<Button variant="outline" onClick={async () => { await api.post("/notifications/read-all"); qc.invalidateQueries({ queryKey: ["notifications"] }); }}>Mark all read</Button>} />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader title="Notifications" description={`${n.data?.unread ?? 0} unread`} /><CardBody className="space-y-1">
          {n.isError ? <ErrorState error={n.error} /> : n.isLoading ? <Skeleton className="h-40" /> : n.data.items.length === 0 ? <EmptyState title="You're all caught up" image={IMAGES.emptyStates.quiet} /> : n.data.items.map((x: any) => {
            const I = ICON[x.kind] || Info;
            return <button key={x.id} onClick={() => open(x)} className={cn("flex w-full items-start gap-3 rounded-xl p-3 text-left hover:bg-muted", !x.read && "bg-accent/5")}><I className={cn("mt-0.5 h-4 w-4 shrink-0", x.kind === "success" && "text-success", (x.kind === "warning" || x.kind === "error") && "text-warning", x.kind === "info" && "text-accent")} /><span className="min-w-0 flex-1"><span className="flex items-center gap-2 text-sm font-medium">{x.title}{!x.read && <span className="h-1.5 w-1.5 rounded-full bg-accent" />}</span>{x.body && <span className="mt-0.5 block text-sm text-muted-foreground">{x.body}</span>}<span className="text-xs text-muted-foreground">{timeAgo(x.created_at)}</span></span></button>;
          })}
        </CardBody></Card>
        <Card><CardHeader title="Workspace activity" /><CardBody>
          {act.isLoading ? <Skeleton className="h-40" /> : <ol className="relative space-y-4 border-l pl-6">{act.data?.items.map((a: any) => <li key={a.id} className="relative"><span className="absolute -left-[31px] top-1.5 h-3 w-3 rounded-full border-2 border-card bg-accent" /><p className="text-sm"><span className="font-medium">{a.action.replace(/\./g, " › ").replace(/_/g, " ")}</span>{(a.details?.name || a.details?.key) && <span className="text-muted-foreground"> · {a.details.name || a.details.key}</span>}</p><p className="text-xs text-muted-foreground">{a.user_email?.split("@")[0] || "system"} · {timeAgo(a.created_at)}</p></li>)}</ol>}
        </CardBody></Card>
      </div>
    </div>
  );
}
