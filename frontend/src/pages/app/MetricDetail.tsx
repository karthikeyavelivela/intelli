import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Check, History, Pencil, Send, ShieldX, X } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { BackLink, CodeBlock, ErrorState, PageHeader } from "@/components/common";
import { MetricForm, draftPayload, toDraft, type MetricDraft } from "@/components/MetricForm";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDateTime, timeAgo } from "@/lib/utils";

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return <div className="grid gap-1 border-b py-3 last:border-0 sm:grid-cols-[170px_1fr] sm:gap-4"><dt className="text-sm text-muted-foreground">{k}</dt><dd className="min-w-0 break-words text-sm">{children || <span className="text-muted-foreground">—</span>}</dd></div>;
}

export default function MetricDetail() {
  const { id } = useParams();
  const { can, user } = useAuth();
  const qc = useQueryClient();
  const nav = useNavigate();
  const toast = useToast();
  const [edit, setEdit] = useState(false);
  const [draft, setDraft] = useState<MetricDraft | null>(null);
  const [reason, setReason] = useState("");
  const [dialog, setDialog] = useState<null | "reject" | "approve" | "publish" | "deprecate" | "submit">(null);
  const [comment, setComment] = useState("");
  const q = useQuery({ queryKey: ["metric", id], queryFn: () => api.get(`/metrics/${id}`) });
  const m = q.data;
  const refresh = () => { qc.invalidateQueries({ queryKey: ["metric", id] }); qc.invalidateQueries({ queryKey: ["metrics"] }); qc.invalidateQueries({ queryKey: ["overview"] }); };

  const act = useMutation({
    mutationFn: ({ action, replace }: { action: string; replace?: boolean }) => api.post(`/metrics/${id}/${action}`, { comment: comment || null, replace: !!replace }),
    onSuccess: (_r, v) => { toast.success(`Metric ${({ submit: "submitted", approve: "approved", reject: "rejected", publish: "published", deprecate: "deprecated" } as any)[v.action]}`); setDialog(null); setComment(""); refresh(); },
    onError: (e: ApiError) => toast.error("Action failed", e.message),
  });
  const save = useMutation({
    mutationFn: () => api.patch(`/metrics/${id}`, { ...draftPayload(draft!), reason: reason || null }),
    onSuccess: (r) => { toast.success("Saved", `New version v${r.version} recorded`); setEdit(false); setReason(""); refresh(); },
    onError: (e: ApiError) => toast.error("Could not save", e.message),
  });

  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!m) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-64" /></div>;

  const editable = can("metric.write") && m.status !== "deprecated";
  const reviewer = can("metric.review");
  const selfApprove = m.owner_id === user?.id && user?.role !== "admin";
  const publishConflict = (act.error as ApiError | null)?.status === 409 && dialog === "publish";

  return (
    <div>
      <BackLink to="/app/metrics">Metrics catalog</BackLink>
      <PageHeader
        title={<span className="flex flex-wrap items-center gap-3">{m.name}<StatusBadge status={m.status} />{m.is_live && <Badge tone="success">live v{m.published_version}</Badge>}{m.source === "tara" && <Badge tone="accent">TARA suggestion</Badge>}</span>}
        description={m.description || "No description"}
        actions={<>
          <Link to={`/app/versions/${m.id}`}><Button variant="outline"><History className="h-4 w-4" />History</Button></Link>
          {editable && <Button variant="outline" onClick={() => { setDraft(toDraft(m)); setEdit(true); }} data-testid="edit-metric"><Pencil className="h-4 w-4" />Edit</Button>}
          {can("metric.write") && m.status === "draft" && <Button onClick={() => setDialog("submit")} data-testid="submit-review"><Send className="h-4 w-4" />Submit for approval</Button>}
          {reviewer && m.status === "in_review" && <>
            <Button variant="outline" onClick={() => setDialog("reject")} data-testid="reject"><X className="h-4 w-4" />Reject</Button>
            <Button variant="accent" onClick={() => setDialog("approve")} disabled={selfApprove} title={selfApprove ? "You cannot approve your own metric" : undefined} data-testid="approve"><Check className="h-4 w-4" />Approve</Button>
          </>}
          {reviewer && m.status === "approved" && <Button onClick={() => setDialog("publish")} data-testid="publish">Publish</Button>}
          {reviewer && m.status !== "deprecated" && m.status !== "draft" && <Button variant="ghost" onClick={() => setDialog("deprecate")}><ShieldX className="h-4 w-4" />Deprecate</Button>}
        </>}
      />
      {m.has_unpublished_changes && <div className="mb-4 flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />Working copy is v{m.version}. Dashboards and Ask TARA keep using the live published v{m.published_version} until the new version is approved and published.</div>}

      <Tabs defaultValue="definition">
        <TabsList><TabsTrigger value="definition">Definition</TabsTrigger><TabsTrigger value="deps">Dependencies</TabsTrigger><TabsTrigger value="reviews">Workflow</TabsTrigger></TabsList>
        <TabsContent value="definition" className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Governed definition" />
            <CardBody>
              <CodeBlock className="text-sm">{m.formula}{m.filters ? `\nWHERE ${m.filters}` : ""}</CodeBlock>
              <dl className="mt-3">
                <Row k="Business definition">{m.business_definition}</Row>
                <Row k="Aggregation">{m.aggregation}</Row>
                <Row k="Unit">{m.unit}</Row>
                <Row k="Time window">{m.time_window?.replace(/_/g, " ")}{m.date_column ? ` on ${m.date_column}` : ""}</Row>
                <Row k="Dataset">{m.dataset_id ? <Link className="text-accent hover:underline" to={`/app/datasets/${m.dataset_id}`}>{m.dataset_name}</Link> : null}</Row>
              </dl>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Ownership" />
            <CardBody><dl>
              <Row k="Owner">{m.owner_name}</Row><Row k="Department">{m.department}</Row><Row k="Category">{m.category}</Row><Row k="Key"><code className="rounded bg-muted px-1.5 py-0.5 text-xs">{m.key}</code></Row>
              <Row k="Working version">v{m.version}</Row><Row k="Published version">{m.published_version ? `v${m.published_version}` : "never published"}</Row><Row k="Updated">{fmtDateTime(m.updated_at)}</Row>
            </dl></CardBody>
          </Card>
        </TabsContent>
        <TabsContent value="deps" className="grid gap-4 md:grid-cols-2">
          <Card><CardHeader title="Uses" description="Metrics referenced by this formula" /><CardBody className="space-y-2">
            {m.depends_on.length === 0 ? <p className="text-sm text-muted-foreground">This metric is defined directly on dataset columns.</p> : m.depends_on.map((d: string) => { const hit = m.depends_on_metrics.find((x: any) => x.name.toLowerCase() === d.toLowerCase() || x.key === d.toLowerCase()); return <div key={d} className="flex items-center justify-between rounded-xl border p-3 text-sm"><span>[{d}]</span>{hit ? <Link className="text-accent hover:underline" to={`/app/metrics/${hit.id}`}>open <ArrowRight className="inline h-3 w-3" /></Link> : <Badge tone="warning">not live</Badge>}</div>; })}
          </CardBody></Card>
          <Card><CardHeader title="Used by" description="Metrics and dashboards that depend on this one" /><CardBody className="space-y-2">
            {m.dependents.map((x: any) => <Link key={x.id} to={`/app/metrics/${x.id}`} className="flex items-center justify-between rounded-xl border p-3 text-sm hover:bg-muted"><span>{x.name}</span><StatusBadge status={x.status} /></Link>)}
            {m.dashboards.map((x: any) => <Link key={x.id} to={`/app/dashboards/${x.id}`} className="flex items-center justify-between rounded-xl border p-3 text-sm hover:bg-muted"><span>{x.name}</span><Badge tone="outline">dashboard</Badge></Link>)}
            {!m.dependents.length && !m.dashboards.length && <p className="text-sm text-muted-foreground">Nothing depends on this metric yet.</p>}
          </CardBody></Card>
          {m.same_key.length > 0 && <Card className="md:col-span-2"><CardHeader title="Other definitions of this metric" description="Same governed key, different department or status. Candidates for conflict detection." /><CardBody className="space-y-2">
            {m.same_key.map((x: any) => <Link key={x.id} to={`/app/metrics/${x.id}`} className="flex items-center justify-between rounded-xl border p-3 text-sm hover:bg-muted"><span>{x.name} · {x.department || "no department"}</span><span className="flex gap-2">{x.is_live && <Badge tone="success">live</Badge>}<StatusBadge status={x.status} /></span></Link>)}
          </CardBody></Card>}
        </TabsContent>
        <TabsContent value="reviews"><Card><CardHeader title="Approval workflow" description="Submit → approve/reject → publish. Every step is recorded." /><CardBody>
          {m.reviews.length === 0 ? <p className="text-sm text-muted-foreground">No workflow events yet.</p> : <ol className="relative space-y-4 border-l pl-6">
            {m.reviews.map((r: any) => <li key={r.id} className="relative"><span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-card bg-accent" /><p className="text-sm"><span className="font-medium capitalize">{r.decision}</span> · v{r.version} · {r.user || "system"} <span className="text-muted-foreground">· {timeAgo(r.at)}</span></p>{r.comment && <p className="mt-0.5 text-sm text-muted-foreground">“{r.comment}”</p>}</li>)}
          </ol>}
        </CardBody></Card></TabsContent>
      </Tabs>

      <Modal open={edit} onOpenChange={setEdit} title={`Edit ${m.name}`} description="Saving creates a new immutable version. Approved or published metrics return to draft for re-review (the published version stays live)." className="max-w-3xl"
        footer={<><Button variant="ghost" onClick={() => setEdit(false)}>Cancel</Button><Button onClick={() => save.mutate()} loading={save.isPending} data-testid="mf-save">Save new version</Button></>}>
        {draft && <MetricForm value={draft} onChange={setDraft} showReason reason={reason} onReason={setReason} />}
      </Modal>

      <Modal open={!!dialog} onOpenChange={(o) => !o && setDialog(null)} title={dialog ? `${dialog[0].toUpperCase()}${dialog.slice(1)} metric` : ""} description={dialog === "reject" ? "A comment is required so the author knows what to fix." : undefined}
        footer={<>
          <Button variant="ghost" onClick={() => setDialog(null)}>Cancel</Button>
          {publishConflict && <Button variant="danger" onClick={() => act.mutate({ action: "publish", replace: true })}>Replace current published</Button>}
          <Button variant={dialog === "deprecate" || dialog === "reject" ? "danger" : "accent"} loading={act.isPending} disabled={dialog === "reject" && !comment.trim()} onClick={() => act.mutate({ action: dialog! })} data-testid="dialog-confirm">Confirm {dialog}</Button>
        </>}>
        <Textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder={dialog === "reject" ? "What needs to change?" : "Optional comment"} aria-label="Comment" data-testid="dialog-comment" />
        {publishConflict && <p role="alert" className="mt-3 text-sm text-danger">{(act.error as ApiError).message}</p>}
      </Modal>
    </div>
  );
}
