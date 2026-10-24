import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, GitCompare, Radar, ShieldAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { DataTable, EmptyState, ErrorState, PageHeader, Pager, TableSkeleton } from "@/components/common";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, timeAgo } from "@/lib/utils";

const SEV_TONE: Record<string, string> = { critical: "bg-danger text-white", high: "bg-danger/15 text-danger", medium: "bg-warning/15 text-warning", low: "bg-muted text-muted-foreground" };

export default function Conflicts() {
  const { can, user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [sp, setSp] = useSearchParams();
  const [status, setStatus] = useState("active");
  const [severity, setSeverity] = useState("");
  const [mine, setMine] = useState(false);
  const [page, setPage] = useState(1);
  const list = useQuery({
    queryKey: ["conflicts", status, severity, mine, page],
    queryFn: () => api.get(`/conflicts${qs({ status: status === "all" ? "" : status, severity, assignee_id: mine ? "me" : "", page, page_size: 20 })}`),
    placeholderData: (p) => p,
  });
  const detect = useMutation({
    mutationFn: () => api.post("/conflicts/detect"),
    onSuccess: (r) => {
      toast.success(r.created + r.updated ? `${r.created} new, ${r.updated} updated conflicts` : "No new conflicts found", r.tara?.note || undefined);
      qc.invalidateQueries({ queryKey: ["conflicts"] }); qc.invalidateQueries({ queryKey: ["overview"] }); setPage(1);
    },
    onError: (e: ApiError) => toast.error("Detection failed", e.message),
  });
  useEffect(() => { if (sp.get("detect") === "1" && can("conflict.detect")) { sp.delete("detect"); setSp(sp, { replace: true }); detect.mutate(); } /* eslint-disable-next-line */ }, []);
  const s = list.data?.summary;

  return (
    <div>
      <PageHeader title="Conflict detection center" description="Definitions are compared structurally across departments and against the published layer. Conflicts move through assign → review → approve → resolve with a full audit trail."
        actions={can("conflict.detect") && <Button variant="accent" onClick={() => detect.mutate()} loading={detect.isPending} data-testid="detect"><Radar className="h-4 w-4" />Run conflict detection</Button>} />
      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[["Active", s?.active, ShieldAlert], ["Critical / High", (s?.by_severity?.critical || 0) + (s?.by_severity?.high || 0), GitCompare], ["Medium / Low", (s?.by_severity?.medium || 0) + (s?.by_severity?.low || 0), GitCompare], ["Resolved", s?.resolved, Bot]].map(([k, v, I]: any) => (
          <Card key={k} className="flex items-center justify-between p-4"><div><p className="text-xs text-muted-foreground">{k}</p><p className="mt-1 text-2xl font-semibold tabular-nums">{v ?? "—"}</p></div><I className="h-5 w-5 text-accent" /></Card>
        ))}
      </div>
      <Card className="mb-4 flex flex-wrap items-center gap-2 p-3">
        <Select value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }} className="w-44" aria-label="Status"><option value="active">Active</option><option value="all">All</option><option value="open">Open</option><option value="assigned">Assigned</option><option value="in_review">In review</option><option value="approved">Approved</option><option value="resolved">Resolved</option><option value="dismissed">Dismissed</option></Select>
        <Select value={severity} onChange={(e) => { setSeverity(e.target.value); setPage(1); }} className="w-40" aria-label="Severity"><option value="">Any severity</option><option value="critical">Critical</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option></Select>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={mine} onChange={(e) => { setMine(e.target.checked); setPage(1); }} className="h-4 w-4 accent-[hsl(var(--accent))]" />Assigned to me</label>
      </Card>
      {list.isError ? <ErrorState error={list.error} retry={() => list.refetch()} /> : list.isLoading ? <Card><TableSkeleton /></Card> : (
        <Card>
          <DataTable rows={list.data.items} rowKey={(c: any) => c.id} onRowClick={(c: any) => nav(`/app/conflicts/${c.id}`)}
            empty={<EmptyState title={status === "active" ? "No active conflicts" : "Nothing here"} description={s && s.active + s.resolved === 0 ? "Run conflict detection to compare every department's metric definitions." : "No conflicts match these filters."} image={IMAGES.features.conflicts} action={can("conflict.detect") && <Button onClick={() => detect.mutate()} loading={detect.isPending}>Run detection</Button>} />}
            columns={[
              { key: "sev", header: "Severity", cell: (c: any) => <span className={cn("rounded-full px-2.5 py-0.5 text-xs font-semibold capitalize", SEV_TONE[c.severity])}>{c.severity}</span> },
              { key: "m", header: "Metric", cell: (c: any) => <div><span className="font-medium">{c.metric_a?.name}</span>{c.has_tara_suggestion && <Badge tone="accent" className="ml-2">TARA suggestion</Badge>}<p className="text-xs text-muted-foreground">{c.metric_a?.department || "—"} (ref) vs {c.metric_b?.department || "—"}</p></div> },
              { key: "t", header: "Differences", cell: (c: any) => <div className="flex flex-wrap gap-1">{[...new Set(c.differences.map((d: any) => d.type))].map((t: any) => <Badge key={t} tone="outline">{t.replace("_", " ")}</Badge>)}</div> },
              { key: "st", header: "Status", cell: (c: any) => <StatusBadge status={c.status} /> },
              { key: "as", header: "Assignee", cell: (c: any) => c.assignee_name || <span className="text-muted-foreground">—</span> },
              { key: "d", header: "Detected", cell: (c: any) => <span className="text-muted-foreground">{timeAgo(c.detected_at)}</span> },
            ]} />
          <Pager page={page} pageSize={20} total={list.data.total} onPage={setPage} />
        </Card>
      )}
    </div>
  );
}
