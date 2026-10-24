import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { LayoutGrid, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, PageHeader } from "@/components/common";
import { SafeImage } from "@/components/SafeImage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Field, Input } from "@/components/ui/form";
import { Skeleton } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/utils";

const TEMPLATE_IMG: Record<string, any> = { sales: IMAGES.templates.sales, finance: IMAGES.templates.finance, operations: IMAGES.templates.operations };

export default function Dashboards() {
  const { can } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [del, setDel] = useState<any>(null);
  const list = useQuery({ queryKey: ["dashboards"], queryFn: () => api.get("/dashboards") });
  const tpl = useQuery({ queryKey: ["dashboard-templates"], queryFn: () => api.get("/dashboards/templates") });
  const created = (d: any) => { qc.invalidateQueries({ queryKey: ["dashboards"] }); nav(`/app/dashboards/${d.id}`); };
  const create = useMutation({ mutationFn: () => api.post("/dashboards", { name, widgets: [], filters: { range: "this_fy" } }), onSuccess: created, onError: (e: ApiError) => toast.error("Could not create", e.message) });
  const fromTpl = useMutation({
    mutationFn: (t: string) => api.post("/dashboards/from-template", { template: t }),
    onSuccess: (d) => { if (d.skipped_metrics?.length) toast.toast({ kind: "info", title: "Some widgets skipped", description: `Missing metrics: ${d.skipped_metrics.join(", ")}` }); created(d); },
    onError: (e: ApiError) => toast.error("Template unavailable", e.message),
  });
  const remove = useMutation({ mutationFn: (id: string) => api.del(`/dashboards/${id}`), onSuccess: () => { toast.success("Dashboard deleted"); setDel(null); qc.invalidateQueries({ queryKey: ["dashboards"] }); } });
  const write = can("dashboard.write");

  return (
    <div>
      <PageHeader title="Dashboards" description="Build dashboards from governed metrics. Widgets follow the latest published definition, or a version you pin." actions={write && <Button onClick={() => setCreating(true)} data-testid="new-dashboard"><Plus className="h-4 w-4" />New dashboard</Button>} />
      <h2 className="mb-3 text-sm font-semibold">Saved dashboards</h2>
      {list.isError ? <ErrorState error={list.error} /> : list.isLoading ? <div className="grid gap-4 md:grid-cols-3"><Skeleton className="h-36 rounded-2xl" /><Skeleton className="h-36 rounded-2xl" /></div> : list.data.items.length === 0 ? (
        <EmptyState title="No dashboards yet" description="Start from a template below or create a blank dashboard." image={IMAGES.emptyStates.generic} />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.data.items.map((d: any) => (
            <Card key={d.id} hover className="group relative p-5" data-testid="dashboard-card">
              <Link to={`/app/dashboards/${d.id}`} className="absolute inset-0 z-10 rounded-2xl" aria-label={`Open ${d.name}`} />
              <div className="flex items-start justify-between gap-2"><LayoutGrid className="h-5 w-5 text-accent" />{d.template && <Badge tone="outline">{d.template} template</Badge>}</div>
              <h3 className="mt-3 font-semibold">{d.name}</h3>
              <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-muted-foreground">{d.description || "No description"}</p>
              <p className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">{d.widget_count} widgets · {d.version_policy === "pinned" ? "pinned versions" : "latest published"} · {timeAgo(d.updated_at)}
                {write && <button className="relative z-20 ml-auto rounded-lg p-1.5 opacity-0 hover:bg-muted group-hover:opacity-100 focus-visible:opacity-100" aria-label={`Delete ${d.name}`} onClick={() => setDel(d)}><Trash2 className="h-4 w-4" /></button>}</p>
            </Card>
          ))}
        </div>
      )}
      {write && <>
        <h2 className="mb-3 mt-10 text-sm font-semibold">Templates</h2>
        <div className="grid gap-4 md:grid-cols-3">
          {tpl.data?.items.map((t: any) => (
            <Card key={t.id} hover className="overflow-hidden" data-testid={`template-${t.id}`}>
              <SafeImage image={TEMPLATE_IMG[t.id] || IMAGES.templates.sales} className="h-36" />
              <div className="p-5"><h3 className="font-semibold">{t.name}</h3><p className="mt-1 text-sm text-muted-foreground">{t.description}</p><p className="mt-2 text-xs text-muted-foreground">{t.widget_count} widgets</p>
                <Button className="mt-4 w-full" variant="outline" loading={fromTpl.isPending && fromTpl.variables === t.id} onClick={() => fromTpl.mutate(t.id)} data-testid={`use-template-${t.id}`}>Use template</Button></div>
            </Card>
          ))}
        </div>
      </>}
      <Modal open={creating} onOpenChange={setCreating} title="New dashboard" footer={<><Button variant="ghost" onClick={() => setCreating(false)}>Cancel</Button><Button disabled={name.trim().length < 2} loading={create.isPending} onClick={() => create.mutate()} data-testid="create-dashboard">Create</Button></>}>
        <Field label="Name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder="Executive summary" autoFocus data-testid="dashboard-name" />}</Field>
      </Modal>
      <Modal open={!!del} onOpenChange={(o) => !o && setDel(null)} title="Delete dashboard?" description={`“${del?.name}” will be removed. Metrics are not affected.`} footer={<><Button variant="ghost" onClick={() => setDel(null)}>Cancel</Button><Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate(del.id)}>Delete</Button></>}><></></Modal>
    </div>
  );
}
