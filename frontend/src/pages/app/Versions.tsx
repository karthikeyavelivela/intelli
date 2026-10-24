import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitCommitVertical, RotateCcw } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CodeBlock, DataTable, EmptyState, ErrorState, FormulaDiff, PageHeader } from "@/components/common";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Select, Textarea } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, fmtDateTime, timeAgo } from "@/lib/utils";

function MetricHistory({ id }: { id: string }) {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [from, setFrom] = useState<number | null>(null);
  const [to, setTo] = useState<number | null>(null);
  const [rb, setRb] = useState<any>(null);
  const [reason, setReason] = useState("");
  const q = useQuery({ queryKey: ["versions", id], queryFn: () => api.get(`/metrics/${id}/versions`) });
  const audit = useQuery({ queryKey: ["metric-audit", id], queryFn: () => api.get(`/metrics/${id}/audit`) });
  const items: any[] = q.data?.items || [];
  useEffect(() => { if (items.length >= 2 && from === null) { setTo(items[0].number); setFrom(items[1].number); } else if (items.length === 1 && from === null) { setFrom(items[0].number); setTo(items[0].number); } }, [items.length]); // eslint-disable-line
  const diff = useQuery({ queryKey: ["diff", id, from, to], enabled: from !== null && to !== null && from !== to, queryFn: () => api.get(`/metrics/${id}/diff?from_version=${from}&to_version=${to}`) });
  const rollback = useMutation({
    mutationFn: () => api.post(`/metrics/${id}/rollback`, { to_version: rb.number, reason }),
    onSuccess: (m) => { toast.success(`Rolled back as new version v${m.version}`, "History is preserved; nothing was overwritten."); setRb(null); setReason(""); qc.invalidateQueries({ queryKey: ["versions", id] }); qc.invalidateQueries({ queryKey: ["metric-audit", id] }); qc.invalidateQueries({ queryKey: ["metrics"] }); },
    onError: (e: ApiError) => toast.error("Rollback failed", e.message),
  });
  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data) return <Skeleton className="h-96" />;
  const m = q.data.metric;
  const merged: any[] = audit.data?.items || [];

  return (
    <div>
      <PageHeader title={<span className="flex flex-wrap items-center gap-3">{m.name}<StatusBadge status={m.status} /></span>} description={`Working version v${m.version}${m.published_version ? ` · live v${m.published_version}` : " · never published"}. Versions are immutable.`}
        actions={<Link to={`/app/metrics/${m.id}`}><Button variant="outline">Open metric</Button></Link>} />
      <Tabs defaultValue="history">
        <TabsList><TabsTrigger value="history">History</TabsTrigger><TabsTrigger value="compare">Compare</TabsTrigger><TabsTrigger value="audit">Audit timeline</TabsTrigger></TabsList>
        <TabsContent value="history">
          <ol className="relative space-y-3 border-l pl-7">
            {items.map((v) => (
              <li key={v.id} className="relative">
                <span className={cn("absolute -left-[37px] top-4 flex h-5 w-5 items-center justify-center rounded-full border-2 border-card", v.is_live ? "bg-success" : "bg-accent")}><GitCommitVertical className="h-3 w-3 text-white" /></span>
                <Card className="p-4" data-testid="version-row">
                  <div className="flex flex-wrap items-center gap-2"><Badge tone="solid" className="font-mono">v{v.number}</Badge>{v.is_live && <Badge tone="success">live</Badge>}{v.was_published && !v.is_live && <Badge tone="outline">was published</Badge>}{v.rollback_of && <Badge tone="warning">rollback of v{v.rollback_of}</Badge>}<span className="text-sm font-medium">{v.change_summary}</span>
                    {can("metric.rollback") && v.number !== m.version && <Button size="sm" variant="outline" className="ml-auto" onClick={() => setRb(v)} data-testid={`rollback-${v.number}`}><RotateCcw className="h-3.5 w-3.5" />Roll back to this</Button>}</div>
                  <p className="mt-1 text-xs text-muted-foreground">{v.author || "system"} · {fmtDateTime(v.created_at)}{v.reason ? ` · “${v.reason}”` : ""}</p>
                  <CodeBlock className="mt-3">{v.snapshot.formula}{v.snapshot.filters ? `\nWHERE ${v.snapshot.filters}` : ""}</CodeBlock>
                  {v.approvals.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{v.approvals.map((a: any, i: number) => <Badge key={i} tone={a.decision === "reject" ? "danger" : a.decision === "publish" ? "success" : "outline"} title={a.comment || ""}>{a.decision} · {a.user || "?"}</Badge>)}</div>}
                </Card>
              </li>
            ))}
          </ol>
        </TabsContent>
        <TabsContent value="compare">
          <Card><CardBody className="space-y-4 pt-5">
            <div className="flex flex-wrap items-center gap-3 text-sm">Compare <Select className="w-28" value={from ?? ""} onChange={(e) => setFrom(Number(e.target.value))} aria-label="From version">{items.map((v) => <option key={v.number} value={v.number}>v{v.number}</option>)}</Select> with <Select className="w-28" value={to ?? ""} onChange={(e) => setTo(Number(e.target.value))} aria-label="To version">{items.map((v) => <option key={v.number} value={v.number}>v{v.number}</option>)}</Select></div>
            {!diff.data ? <p className="text-sm text-muted-foreground">Pick two different versions to see what changed.</p> : diff.data.changes.length === 0 ? <p className="text-sm text-muted-foreground">These versions are identical.</p> : (<>
              <div className="grid gap-3 md:grid-cols-2"><div><p className="mb-1.5 text-xs font-medium text-muted-foreground">v{from} formula</p><FormulaDiff segments={diff.data.formula_diff} side="a" /></div><div><p className="mb-1.5 text-xs font-medium text-muted-foreground">v{to} formula</p><FormulaDiff segments={diff.data.formula_diff} side="b" /></div></div>
              <DataTable dense rows={diff.data.changes} rowKey={(c: any) => c.field} columns={[{ key: "f", header: "Field", cell: (c: any) => <code>{c.field}</code> }, { key: "a", header: `v${from}`, cell: (c: any) => <span className="break-words font-mono text-xs text-danger">{String(c.from ?? "—")}</span> }, { key: "b", header: `v${to}`, cell: (c: any) => <span className="break-words font-mono text-xs text-success">{String(c.to ?? "—")}</span> }]} />
            </>)}
          </CardBody></Card>
        </TabsContent>
        <TabsContent value="audit"><Card><CardBody className="pt-5">
          {merged.length === 0 ? <p className="text-sm text-muted-foreground">No audit entries.</p> : <ol className="relative space-y-4 border-l pl-6">{merged.map((a) => <li key={a.id} className="relative"><span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-card bg-accent" /><p className="text-sm"><span className="font-medium">{a.action.replace("metric.", "").replace(/_/g, " ")}</span> <span className="text-muted-foreground">· {a.user_email?.split("@")[0] || "system"} · {timeAgo(a.created_at)}</span></p>{a.details?.comment && <p className="text-sm text-muted-foreground">“{a.details.comment}”</p>}{a.details?.reason && <p className="text-sm text-muted-foreground">“{a.details.reason}”</p>}{a.details?.changes && <p className="text-xs text-muted-foreground">changed: {a.details.changes.map((c: any) => c.field).join(", ")}</p>}</li>)}</ol>}
        </CardBody></Card></TabsContent>
      </Tabs>
      <Modal open={!!rb} onOpenChange={(o) => !o && setRb(null)} title={`Roll back to v${rb?.number}?`} description="This creates a NEW version with the old definition. Existing versions are never changed or deleted. If the metric is live, the rollback becomes the live definition immediately."
        footer={<><Button variant="ghost" onClick={() => setRb(null)}>Cancel</Button><Button variant="accent" disabled={reason.trim().length < 3} loading={rollback.isPending} onClick={() => rollback.mutate()} data-testid="rollback-confirm">Create rollback version</Button></>}>
        {rb && <CodeBlock className="mb-3">{rb.snapshot.formula}</CodeBlock>}
        <Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Reason (required)" aria-label="Reason" data-testid="rollback-reason" />
      </Modal>
    </div>
  );
}

export default function Versions() {
  const { id } = useParams();
  const nav = useNavigate();
  const metrics = useQuery({ queryKey: ["metrics", "all-versions"], queryFn: () => api.get("/metrics?page_size=100&sort=name") });
  const recent = useQuery({ queryKey: ["recent-versions"], queryFn: () => api.get("/versions/recent?limit=20") });
  return (
    <div>
      {!id && <PageHeader title="Version control" description="Immutable history for every metric. Compare versions, roll back by creating a new version, and follow the audit timeline." />}
      <div className="mb-5 flex flex-wrap items-center gap-3"><label className="text-sm font-medium" htmlFor="metric-pick">Metric</label>
        <Select id="metric-pick" className="w-72" value={id || ""} onChange={(e) => nav(e.target.value ? `/app/versions/${e.target.value}` : "/app/versions")} data-testid="version-metric"><option value="">Choose a metric…</option>{metrics.data?.items.map((m: any) => <option key={m.id} value={m.id}>{m.name}{m.department ? ` (${m.department})` : ""} · v{m.version}</option>)}</Select></div>
      {id ? <MetricHistory id={id} key={id} /> : (
        <Card><CardHeader title="Recent changes across the workspace" />
          {recent.data?.items.length ? <DataTable dense rows={recent.data.items} rowKey={(r: any) => `${r.metric_id}${r.number}`} onRowClick={(r: any) => nav(`/app/versions/${r.metric_id}`)} columns={[{ key: "m", header: "Metric", cell: (r: any) => <span className="font-medium">{r.metric_name}</span> }, { key: "v", header: "Version", cell: (r: any) => <Badge tone="outline" className="font-mono">v{r.number}</Badge> }, { key: "s", header: "Change", cell: (r: any) => r.change_summary }, { key: "a", header: "Author", cell: (r: any) => r.author || "system" }, { key: "t", header: "When", cell: (r: any) => <span className="text-muted-foreground">{timeAgo(r.created_at)}</span> }]} /> : <EmptyState title="No versions yet" image={IMAGES.features.versions} />}
        </Card>
      )}
    </div>
  );
}
