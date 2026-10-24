import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, Lightbulb, UserCheck } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BackLink, ErrorState, FormulaDiff, PageHeader } from "@/components/common";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, fmtDateTime } from "@/lib/utils";

const STEPS = ["open", "assigned", "in_review", "approved", "resolved"];
const ACTIONS: Record<string, [string, string]> = {
  rename_variant: ["Rename the variant", "Keep the published definition; give the variant its own distinct name and key."],
  align_to_published: ["Align variant to published", "Copy formula, filters, unit and scope from the published definition into the variant."],
  deprecate_variant: ["Deprecate the variant", "Retire the conflicting definition."],
  accept_both: ["Accept both (documented)", "Keep both definitions as intentional; the decision is recorded."],
};

function MetricCard({ title, m, full }: { title: string; m: any; full: any }) {
  return (
    <Card className="min-w-0">
      <CardHeader title={<span className="flex flex-wrap items-center gap-2">{title}<StatusBadge status={m.status} />{m.is_live && <Badge tone="success">live</Badge>}</span>} description={<Link className="text-accent hover:underline" to={`/app/metrics/${m.id}`}>{m.name} · {m.department || "no department"}</Link>} />
      <CardBody>
        <dl className="grid grid-cols-[90px_1fr] gap-y-1.5 text-sm"><dt className="text-muted-foreground">Unit</dt><dd>{full.unit || "—"}</dd><dt className="text-muted-foreground">Filters</dt><dd className="break-words font-mono text-xs">{full.filters || "—"}</dd><dt className="text-muted-foreground">Window</dt><dd>{full.time_window.replace(/_/g, " ")}</dd><dt className="text-muted-foreground">Dataset</dt><dd>{full.dataset_name}</dd><dt className="text-muted-foreground">Version</dt><dd className="font-mono text-xs">v{full.version}</dd></dl>
      </CardBody>
    </Card>
  );
}

export default function ConflictDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [modal, setModal] = useState<null | "assign" | "resolve" | "dismiss">(null);
  const [note, setNote] = useState("");
  const [assignee, setAssignee] = useState("");
  const [action, setAction] = useState("rename_variant");
  const [newName, setNewName] = useState("");
  const q = useQuery({ queryKey: ["conflict", id], queryFn: () => api.get(`/conflicts/${id}`) });
  const ev = useQuery({ queryKey: ["conflict-events", id], queryFn: () => api.get(`/conflicts/${id}/events`) });
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get("/users"), enabled: can("conflict.manage") });
  const c = q.data;
  const done = () => { qc.invalidateQueries({ queryKey: ["conflict", id] }); qc.invalidateQueries({ queryKey: ["conflict-events", id] }); qc.invalidateQueries({ queryKey: ["conflicts"] }); qc.invalidateQueries({ queryKey: ["metrics"] }); qc.invalidateQueries({ queryKey: ["overview"] }); setModal(null); setNote(""); };
  const step = useMutation({
    mutationFn: ({ path, body }: { path: string; body: any }) => api.post(`/conflicts/${id}/${path}`, body),
    onSuccess: (_r, v) => { toast.success(`Conflict ${v.path === "resolve" ? "resolved" : v.path === "dismiss" ? "dismissed" : v.path === "assign" ? "assigned" : v.path === "review" ? "moved to review" : v.path + "d"}`); done(); },
    onError: (e: ApiError) => toast.error("Action failed", e.message),
  });

  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!c) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-72" /></div>;
  const manage = can("conflict.manage");
  const idx = STEPS.indexOf(c.status);
  const closed = c.status === "resolved" || c.status === "dismissed";
  const openResolve = () => { setAction(c.recommended_action && ACTIONS[c.recommended_action] ? c.recommended_action : "rename_variant"); setNewName(`${c.metric_b.name} (${c.metric_b.department || "variant"})`); setModal("resolve"); };

  return (
    <div>
      <BackLink to="/app/conflicts">Conflict center</BackLink>
      <PageHeader
        title={<span className="flex flex-wrap items-center gap-3">{c.metric_a.name}: conflicting definitions<StatusBadge status={c.severity} /></span>}
        description={c.explanation}
        actions={manage && !closed && <>
          {["open", "assigned"].includes(c.status) && <Button variant="outline" onClick={() => { setAssignee(c.assignee_id || ""); setModal("assign"); }} data-testid="assign"><UserCheck className="h-4 w-4" />{c.status === "open" ? "Assign" : "Reassign"}</Button>}
          {c.status === "assigned" && <Button onClick={() => step.mutate({ path: "review", body: {} })} loading={step.isPending} data-testid="start-review">Start review</Button>}
          {c.status === "in_review" && <Button variant="accent" onClick={() => step.mutate({ path: "approve", body: { note: "Approved resolution plan" } })} loading={step.isPending} data-testid="approve-conflict"><Check className="h-4 w-4" />Approve</Button>}
          {c.status === "approved" && <Button variant="accent" onClick={openResolve} data-testid="resolve">Resolve…</Button>}
          <Button variant="ghost" onClick={() => setModal("dismiss")}>Dismiss</Button>
        </>}
      />

      <ol className="mb-6 grid grid-cols-5 gap-1 sm:gap-2" aria-label="Workflow progress">
        {STEPS.map((s, i) => <li key={s} className={cn("rounded-xl border px-2 py-2 text-center text-[11px] font-medium capitalize sm:text-xs", i < idx && "border-accent/40 bg-accent/10 text-accent", i === idx && !closed && "border-accent bg-accent text-accent-foreground", c.status === "dismissed" && i === 0 && "opacity-60", i > idx && "text-muted-foreground")} aria-current={i === idx ? "step" : undefined}>{s.replace("_", " ")}</li>)}
      </ol>
      {c.assignee_name && <p className="mb-4 text-sm text-muted-foreground">Assigned to <span className="font-medium text-foreground">{c.assignee_name}</span></p>}

      <div className="grid gap-4 md:grid-cols-2">
        <MetricCard title="Reference" m={c.metric_a} full={c.a_full} />
        <MetricCard title="Variant" m={c.metric_b} full={c.b_full} />
      </div>

      <Card className="mt-4">
        <CardHeader title="Formula diff" description="Highlighted tokens differ between the two definitions" />
        <CardBody className="grid gap-3 md:grid-cols-2"><FormulaDiff segments={c.formula_diff} side="a" /><FormulaDiff segments={c.formula_diff} side="b" /></CardBody>
        {c.a_full.filters !== c.b_full.filters && <CardBody className="grid gap-3 pt-0 md:grid-cols-2"><FormulaDiff segments={c.filters_diff} side="a" /><FormulaDiff segments={c.filters_diff} side="b" /></CardBody>}
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="What differs" />
          <CardBody className="space-y-3">
            {c.differences.map((d: any, i: number) => (
              <div key={i} className="rounded-xl border p-3.5">
                <div className="flex flex-wrap items-center gap-2"><Badge tone="solid" className="capitalize">{d.type.replace("_", " ")}</Badge><StatusBadge status={d.severity} />{d.source === "tara" ? <Badge tone="accent"><Bot className="h-3 w-3" />TARA suggestion</Badge> : <Badge tone="outline">deterministic check</Badge>}</div>
                <p className="mt-2 text-sm">{d.explanation}</p>
                <dl className="mt-2 grid gap-2 text-xs sm:grid-cols-2"><div className="rounded-lg bg-muted/60 p-2"><dt className="text-muted-foreground">A (reference)</dt><dd className="break-words font-mono">{String(d.a)}</dd></div><div className="rounded-lg bg-muted/60 p-2"><dt className="text-muted-foreground">B (variant)</dt><dd className="break-words font-mono">{String(d.b)}</dd></div></dl>
              </div>
            ))}
          </CardBody>
        </Card>
        <div className="space-y-4">
          <Card className="border-accent/40"><CardHeader title={<span className="flex items-center gap-2"><Lightbulb className="h-4 w-4 text-accent" />Recommended resolution</span>} /><CardBody><p className="text-sm">{c.recommendation}</p>{c.recommended_action && <Badge tone="accent" className="mt-3">{ACTIONS[c.recommended_action]?.[0] || c.recommended_action}</Badge>}</CardBody></Card>
          <Card><CardHeader title="Affected" /><CardBody className="space-y-2 text-sm">
            {c.affected.metrics?.length ? c.affected.metrics.map((m: any) => <p key={m.key}>Metric: <span className="font-medium">{m.name}</span></p>) : <p className="text-muted-foreground">No dependent metrics</p>}
            {c.affected.dashboards?.length ? c.affected.dashboards.map((d: any) => <p key={d.id}>Dashboard: <Link className="font-medium text-accent hover:underline" to={`/app/dashboards/${d.id}`}>{d.name}</Link></p>) : <p className="text-muted-foreground">No dashboards use this metric</p>}
          </CardBody></Card>
          {closed && <Card><CardHeader title="Outcome" /><CardBody className="text-sm"><p className="font-medium capitalize">{(c.resolution_action || c.status).replace(/_/g, " ")}</p><p className="mt-1 text-muted-foreground">{c.resolution_note}</p></CardBody></Card>}
        </div>
      </div>

      <Card className="mt-4"><CardHeader title="Audit history" /><CardBody>
        <ol className="relative space-y-4 border-l pl-6">{ev.data?.items.map((e: any) => <li key={e.id} className="relative"><span className="absolute -left-[31px] top-1 h-3 w-3 rounded-full border-2 border-card bg-accent" /><p className="text-sm"><span className="font-medium">{e.action.replace("conflict.", "").replace(/_/g, " ")}</span> <span className="text-muted-foreground">by {e.user_email?.split("@")[0] || "system"} · {fmtDateTime(e.created_at)}</span></p>{(e.details?.note || e.details?.assignee) && <p className="text-sm text-muted-foreground">{e.details.assignee ? `→ ${e.details.assignee}. ` : ""}{e.details.note}</p>}</li>)}</ol>
      </CardBody></Card>

      <Modal open={modal === "assign"} onOpenChange={(o) => !o && setModal(null)} title="Assign conflict" footer={<><Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button><Button disabled={!assignee} loading={step.isPending} onClick={() => step.mutate({ path: "assign", body: { assignee_id: assignee, note } })} data-testid="assign-confirm">Assign</Button></>}>
        <div className="space-y-3"><Field label="Assignee">{(i) => <Select id={i} value={assignee} onChange={(e) => setAssignee(e.target.value)} data-testid="assignee"><option value="">Choose a teammate…</option>{users.data?.items.filter((u: any) => u.is_active).map((u: any) => <option key={u.id} value={u.id}>{u.name} · {u.role_label}</option>)}</Select>}</Field><Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note for the assignee (optional)" aria-label="Note" /></div>
      </Modal>
      <Modal open={modal === "resolve"} onOpenChange={(o) => !o && setModal(null)} title="Resolve conflict" description="The chosen action is applied and recorded as a new metric version." className="max-w-xl"
        footer={<><Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button><Button variant="accent" disabled={note.trim().length < 3 || (action === "rename_variant" && !newName.trim())} loading={step.isPending} onClick={() => step.mutate({ path: "resolve", body: { action, note, new_name: action === "rename_variant" ? newName : null } })} data-testid="resolve-confirm">Apply resolution</Button></>}>
        <div className="space-y-3">
          {Object.entries(ACTIONS).map(([k, [t, d]]) => <label key={k} className={cn("flex cursor-pointer gap-3 rounded-xl border p-3", action === k && "border-accent bg-accent/5")}><input type="radio" name="act" checked={action === k} onChange={() => setAction(k)} className="mt-1 accent-[hsl(var(--accent))]" /><span><span className="block text-sm font-medium">{t}{k === c.recommended_action && <Badge tone="accent" className="ml-2">recommended</Badge>}</span><span className="text-xs text-muted-foreground">{d}</span></span></label>)}
          {action === "rename_variant" && <Field label="New name for the variant">{(i) => <Input id={i} value={newName} onChange={(e) => setNewName(e.target.value)} data-testid="new-name" />}</Field>}
          <Field label="Resolution note (required)">{(i) => <Textarea id={i} value={note} onChange={(e) => setNote(e.target.value)} rows={2} data-testid="resolve-note" placeholder="Why this resolution?" />}</Field>
        </div>
      </Modal>
      <Modal open={modal === "dismiss"} onOpenChange={(o) => !o && setModal(null)} title="Dismiss conflict" description="Use only if this is a false positive. A note is required." footer={<><Button variant="ghost" onClick={() => setModal(null)}>Cancel</Button><Button variant="danger" disabled={!note.trim()} loading={step.isPending} onClick={() => step.mutate({ path: "dismiss", body: { note } })}>Dismiss</Button></>}>
        <Textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason" aria-label="Reason" />
      </Modal>
    </div>
  );
}
