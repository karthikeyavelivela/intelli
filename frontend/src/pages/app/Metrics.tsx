import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch, List, Plus, Search, Workflow } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { DataTable, DemoBadge, EmptyState, ErrorState, PageHeader, Pager, TableSkeleton, useDebounced } from "@/components/common";
import { EMPTY_DRAFT, MetricForm, draftPayload, type MetricDraft } from "@/components/MetricForm";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Input, Select } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, timeAgo } from "@/lib/utils";

const STATUSES = ["draft", "in_review", "approved", "published", "deprecated"];

function DependencyGraph() {
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["metric-graph"], queryFn: () => api.get("/metrics/graph") });
  const layout = useMemo(() => {
    if (!data) return null;
    const nodes: any[] = data.nodes.filter((n: any) => n.status !== "deprecated");
    const depth: Record<string, number> = {};
    const out: Record<string, string[]> = {};
    data.edges.forEach((e: any) => (out[e.from] = [...(out[e.from] || []), e.to]));
    const d = (id: string, seen = new Set<string>()): number => {
      if (depth[id] !== undefined) return depth[id];
      if (seen.has(id)) return 0;
      seen.add(id);
      return (depth[id] = (out[id] || []).length ? 1 + Math.max(...out[id].map((t) => d(t, seen))) : 0);
    };
    nodes.forEach((n) => d(n.id));
    const cols: Record<number, any[]> = {};
    nodes.forEach((n) => (cols[depth[n.id] || 0] = [...(cols[depth[n.id] || 0] || []), n]));
    const pos: Record<string, { x: number; y: number }> = {};
    Object.entries(cols).forEach(([c, ns]) => ns.forEach((n, i) => (pos[n.id] = { x: 30 + Number(c) * 250, y: 24 + i * 52 })));
    const h = Math.max(...Object.values(cols).map((c) => c.length)) * 52 + 40;
    return { nodes, pos, h, w: (Object.keys(cols).length) * 250 + 40, edges: data.edges.filter((e: any) => pos[e.from] && pos[e.to]) };
  }, [data]);
  if (!layout) return <TableSkeleton rows={4} cols={3} />;
  return (
    <Card className="overflow-x-auto p-4">
      <p className="mb-3 text-sm text-muted-foreground">Arrows point from a metric to the metrics its formula references. Click a node to open it.</p>
      <svg width={layout.w} height={layout.h} role="img" aria-label="Metric dependency graph" className="min-w-full">
        <defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="hsl(var(--muted-foreground))" /></marker></defs>
        {layout.edges.map((e: any, i: number) => { const a = layout.pos[e.from], b = layout.pos[e.to]; return <path key={i} d={`M${a.x + 200} ${a.y + 16} C ${a.x + 230} ${a.y + 16}, ${b.x - 30} ${b.y + 16}, ${b.x} ${b.y + 16}`} fill="none" stroke="hsl(var(--muted-foreground))" strokeWidth="1.4" markerEnd="url(#arr)" />; })}
        {layout.nodes.map((n) => { const p = layout.pos[n.id]; return (
          <g key={n.id} transform={`translate(${p.x},${p.y})`} className="cursor-pointer" onClick={() => nav(`/app/metrics/${n.id}`)} tabIndex={0} role="link" aria-label={n.name} onKeyDown={(e) => e.key === "Enter" && nav(`/app/metrics/${n.id}`)}>
            <rect width="200" height="32" rx="10" fill="hsl(var(--card))" stroke={n.status === "published" ? "hsl(var(--accent))" : "hsl(var(--border))"} strokeWidth="1.4" />
            <text x="12" y="20" fontSize="12" fill="hsl(var(--foreground))" fontWeight="500">{n.name.length > 24 ? n.name.slice(0, 23) + "…" : n.name}</text>
          </g>
        ); })}
      </svg>
    </Card>
  );
}

export default function Metrics() {
  const { can, user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [sp, setSp] = useSearchParams();
  const [view, setView] = useState<"list" | "graph">("list");
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [status, setStatus] = useState("");
  const [department, setDepartment] = useState("");
  const [category, setCategory] = useState("");
  const [sort, setSort] = useState("-updated_at");
  const [page, setPage] = useState(1);
  const [creating, setCreating] = useState(sp.get("new") === "1");
  const [draft, setDraft] = useState<MetricDraft>(EMPTY_DRAFT);

  useEffect(() => setPage(1), [dq, status, department, category]);
  const facets = useQuery({ queryKey: ["metric-facets"], queryFn: () => api.get("/metrics/facets") });
  const list = useQuery({
    queryKey: ["metrics", dq, status, department, category, sort, page],
    queryFn: () => api.get(`/metrics${qs({ q: dq, status, department, category, sort, page, page_size: 15 })}`),
    placeholderData: (p) => p,
  });
  const create = useMutation({
    mutationFn: () => api.post("/metrics", draftPayload(draft)),
    onSuccess: (m) => { toast.success("Draft created", `${m.name} saved as v1`); qc.invalidateQueries({ queryKey: ["metrics"] }); setCreating(false); setDraft(EMPTY_DRAFT); nav(`/app/metrics/${m.id}`); },
    onError: (e: ApiError) => toast.error("Could not create metric", e.message),
  });
  const closeCreate = () => { setCreating(false); if (sp.get("new")) { sp.delete("new"); setSp(sp, { replace: true }); } };

  return (
    <div>
      <PageHeader
        title="Metrics catalog"
        description="The semantic layer: one governed definition per business metric. Search, filter and follow each metric from draft to published."
        actions={<>{user?.workspace.is_demo && <DemoBadge />}{can("metric.write") && <Button onClick={() => setCreating(true)} data-testid="new-metric"><Plus className="h-4 w-4" />New metric</Button>}</>}
      />
      <Card className="mb-4 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative min-w-[200px] flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, description, formula…" className="pl-9" aria-label="Search metrics" data-testid="metric-search" />
          </div>
          <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-40" aria-label="Filter by status"><option value="">All statuses</option>{STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</Select>
          <Select value={department} onChange={(e) => setDepartment(e.target.value)} className="w-44" aria-label="Filter by department"><option value="">All departments</option>{facets.data?.departments.map((d: any) => <option key={d.value} value={d.value}>{d.value} ({d.count})</option>)}</Select>
          <Select value={category} onChange={(e) => setCategory(e.target.value)} className="w-40" aria-label="Filter by category"><option value="">All categories</option>{facets.data?.categories.map((d: any) => <option key={d.value} value={d.value}>{d.value} ({d.count})</option>)}</Select>
          <div className="ml-auto inline-flex rounded-xl border bg-muted p-0.5" role="group" aria-label="View">
            <button onClick={() => setView("list")} aria-pressed={view === "list"} className={cn("rounded-lg px-2.5 py-1.5", view === "list" && "bg-card shadow-soft")}><List className="h-4 w-4" aria-label="List view" /></button>
            <button onClick={() => setView("graph")} aria-pressed={view === "graph"} className={cn("rounded-lg px-2.5 py-1.5", view === "graph" && "bg-card shadow-soft")} data-testid="graph-view"><Workflow className="h-4 w-4" aria-label="Dependency graph" /></button>
          </div>
        </div>
      </Card>

      {view === "graph" ? <DependencyGraph /> : list.isError ? <ErrorState error={list.error} retry={() => list.refetch()} /> : (
        <Card>
          {list.isLoading ? <TableSkeleton /> : (
            <>
              <DataTable
                rows={list.data.items} rowKey={(m: any) => m.id} onRowClick={(m: any) => nav(`/app/metrics/${m.id}`)} sort={sort} onSort={setSort}
                empty={<EmptyState title="No metrics match" description="Adjust the filters, or create the first governed metric." image={IMAGES.emptyStates.generic} />}
                columns={[
                  { key: "name", header: "Metric", sortKey: "name", cell: (m: any) => (
                    <div className="min-w-0"><div className="flex items-center gap-2"><span className="font-medium">{m.name}</span>{m.source === "tara" && <Badge tone="accent">TARA</Badge>}{m.has_unpublished_changes && <Badge tone="warning">unpublished edits</Badge>}</div><code className="block max-w-md truncate text-xs text-muted-foreground">{m.formula}</code></div>
                  ) },
                  { key: "status", header: "Status", sortKey: "status", cell: (m: any) => <StatusBadge status={m.status} /> },
                  { key: "dept", header: "Department", sortKey: "department", cell: (m: any) => m.department || <span className="text-muted-foreground">—</span> },
                  { key: "unit", header: "Unit", cell: (m: any) => m.unit || "—" },
                  { key: "dataset", header: "Dataset", cell: (m: any) => <span className="text-muted-foreground">{m.dataset_name || "—"}</span> },
                  { key: "ver", header: "Version", cell: (m: any) => <span className="font-mono text-xs">v{m.version}{m.published_version && m.published_version !== m.version ? ` (live v${m.published_version})` : ""}</span> },
                  { key: "upd", header: "Updated", sortKey: "updated_at", cell: (m: any) => <span className="text-muted-foreground">{timeAgo(m.updated_at)}</span> },
                ]}
              />
              <Pager page={page} pageSize={15} total={list.data.total} onPage={setPage} />
            </>
          )}
        </Card>
      )}

      <Modal open={creating} onOpenChange={(o) => (o ? setCreating(true) : closeCreate())} title="New metric" description="Saved as a draft (v1). Nothing is published until it is submitted and approved." className="max-w-3xl"
        footer={<><Button variant="ghost" onClick={closeCreate}>Cancel</Button><Button onClick={() => create.mutate()} loading={create.isPending} disabled={!draft.name || !draft.formula || !draft.dataset_id} data-testid="mf-save">Save draft</Button></>}>
        <MetricForm value={draft} onChange={setDraft} />
      </Modal>
    </div>
  );
}
