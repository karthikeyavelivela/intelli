import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toPng } from "html-to-image";
import { BarChart3, Check, Download, FileImage, FileText, GripVertical, LineChart as LineIcon, Lock, PieChart as PieIcon, Pencil, Plus, RefreshCw, Save, Table2, Trash2, Hash, Unlock } from "lucide-react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Responsive, WidthProvider, type Layout } from "react-grid-layout";
import { useParams } from "react-router-dom";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import { SeriesChart } from "@/components/charts";
import { AnimatedNumber, BackLink, ErrorState } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/form";
import { Menu, MenuContent, MenuItem, MenuTrigger } from "@/components/ui/dropdown";
import { Skeleton } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, downloadBlob, formatValue, toCsv } from "@/lib/utils";

const Grid = WidthProvider(Responsive);
const RANGES = [["all", "All time"], ["last_30_days", "Last 30 days"], ["last_90_days", "Last 90 days"], ["last_quarter", "Last quarter (fiscal)"], ["this_fy", "This financial year (to date)"], ["last_fy", "Last financial year"], ["last_12_months", "Last 12 months"]];
const TYPES = [["kpi", "KPI card", Hash], ["line", "Line chart", LineIcon], ["bar", "Bar chart", BarChart3], ["pie", "Pie chart", PieIcon], ["table", "Table", Table2]] as const;
const GRAINS = ["day", "week", "month", "quarter", "year"];

function WidgetBody({ w, filters, policy, tick, report }: { w: any; filters: any; policy: string; tick: number; report: (id: string, d: any) => void }) {
  const key = ["widget", w.type, w.metric_key, w.dimension, w.grain, w.limit, w.pinned_version, filters, policy, tick];
  const q = useQuery({ queryKey: key, queryFn: () => api.post("/dashboards/widget-data", { widget: w, filters, version_policy: policy }), staleTime: 60_000 });
  useEffect(() => { if (q.data) report(w.id, { ...q.data, title: w.title, type: w.type }); }, [q.data]); // eslint-disable-line
  if (q.isLoading) return <div className="space-y-2 p-1"><Skeleton className="h-6 w-1/2" /><Skeleton className="h-24" /></div>;
  if (q.isError || !q.data?.ok) return <p role="alert" className="p-2 text-sm text-danger">{(q.data as any)?.error || (q.error as any)?.message || "Failed to load"}</p>;
  const d = q.data;
  const last = (r: any[]) => r[r.length - 1];
  if (w.type === "kpi") return (
    <div className="flex h-full flex-col justify-center">
      <p className="text-3xl font-semibold tabular-nums sm:text-4xl" data-testid="kpi-widget"><AnimatedNumber value={d.rows[0] ? last(d.rows[0]) : null} unit={d.unit} /></p>
      <p className="mt-1 text-xs text-muted-foreground">{d.metric_name} · v{d.version}</p>
    </div>
  );
  const data = d.rows.map((r: any[]) => ({ x: String(r[0]), y: last(r) }));
  if (!data.length) return <p className="p-4 text-center text-sm text-muted-foreground">No data for the selected filters</p>;
  if (w.type === "table") return (
    <div className="h-full overflow-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground"><th className="px-2 py-2 font-medium">{d.dimension || "Group"}</th><th className="px-2 py-2 text-right font-medium">{d.metric_name}</th></tr></thead>
      <tbody>{data.map((r: any, i: number) => <tr key={i} className="border-b last:border-0"><td className="px-2 py-1.5">{r.x.slice(0, 10)}</td><td className="px-2 py-1.5 text-right tabular-nums">{formatValue(r.y, d.unit)}</td></tr>)}</tbody></table></div>
  );
  return <div className="h-full min-h-[120px]"><SeriesChart type={w.type} data={data} unit={d.unit} height={Math.max(140, (w.h || 4) * 56 - 80)} name={d.metric_name} /></div>;
}

function WidgetModal({ open, onClose, initial, onSave, policy }: { open: boolean; onClose: () => void; initial: any; onSave: (w: any) => void; policy: string }) {
  const [w, setW] = useState<any>(initial);
  useEffect(() => setW(initial), [initial]);
  const metrics = useQuery({ queryKey: ["live-metrics-all"], queryFn: () => api.get("/metrics?page_size=100&status=published,approved") });
  const mm = metrics.data?.items.find((m: any) => m.key === w.metric_key);
  const ds = useQuery({ queryKey: ["dataset", mm?.dataset_id], enabled: !!mm?.dataset_id, queryFn: () => api.get(`/datasets/${mm.dataset_id}`) });
  const vers = useQuery({ queryKey: ["versions", mm?.id], enabled: !!mm?.id && policy === "pinned", queryFn: () => api.get(`/metrics/${mm.id}/versions`) });
  const set = (k: string, v: any) => setW((x: any) => ({ ...x, [k]: v || undefined }));
  const cats = (ds.data?.schema || []).filter((c: any) => c.category === "string");
  const dates = (ds.data?.schema || []).filter((c: any) => c.category === "date");
  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title={initial.id ? "Edit widget" : "Add widget"} className="max-w-xl"
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button disabled={!w.metric_key} onClick={() => onSave({ ...w, title: w.title || mm?.name })} data-testid="widget-save">{initial.id ? "Update" : "Add widget"}</Button></>}>
      <div className="space-y-4">
        <div className="grid grid-cols-5 gap-2" role="radiogroup" aria-label="Widget type">{TYPES.map(([t, label, I]) => <button key={t} role="radio" aria-checked={w.type === t} onClick={() => set("type", t)} data-testid={`wtype-${t}`} className={cn("flex flex-col items-center gap-1.5 rounded-xl border p-3 text-xs", w.type === t ? "border-accent bg-accent/10 text-accent" : "hover:bg-muted")}><I className="h-5 w-5" />{label.split(" ")[0]}</button>)}</div>
        <Field label="Metric">{(id) => <Select id={id} value={w.metric_key || ""} onChange={(e) => setW({ ...w, metric_key: e.target.value, dimension: undefined, pinned_version: undefined })} data-testid="widget-metric"><option value="">Select a metric…</option>{metrics.data?.items.filter((m: any) => m.is_live || m.status === "approved").map((m: any) => <option key={m.id} value={m.key}>{m.name}{m.department ? ` · ${m.department}` : ""}</option>)}</Select>}</Field>
        <Field label="Title">{(id) => <Input id={id} value={w.title || ""} onChange={(e) => set("title", e.target.value)} placeholder={mm?.name || "Widget title"} />}</Field>
        {w.type !== "kpi" && (
          <div className="grid grid-cols-2 gap-3">
            {w.type === "line" ? (
              <><Field label="Time grain">{(id) => <Select id={id} value={w.grain || "month"} onChange={(e) => set("grain", e.target.value)}>{GRAINS.map((g) => <option key={g}>{g}</option>)}</Select>}</Field><Field label="Date column">{(id) => <Select id={id} value={w.dimension || ""} onChange={(e) => set("dimension", e.target.value)}><option value="">Dataset default</option>{dates.map((c: any) => <option key={c.name}>{c.name}</option>)}</Select>}</Field></>
            ) : (
              <><Field label="Group by">{(id) => <Select id={id} value={w.dimension || ""} onChange={(e) => set("dimension", e.target.value)}><option value="">Auto</option>{cats.map((c: any) => <option key={c.name}>{c.name}</option>)}</Select>}</Field><Field label="Max rows">{(id) => <Input id={id} type="number" min={1} max={200} value={w.limit || ""} onChange={(e) => set("limit", Number(e.target.value))} placeholder="50" />}</Field></>
            )}
          </div>
        )}
        {policy === "pinned" && mm && <Field label="Pinned version" hint="This dashboard uses pinned versions; pick the metric version this widget reads.">{(id) => <Select id={id} value={w.pinned_version || ""} onChange={(e) => set("pinned_version", Number(e.target.value))}><option value="">Latest published</option>{vers.data?.items.map((v: any) => <option key={v.number} value={v.number}>v{v.number}{v.is_live ? " (live)" : ""} · {v.change_summary}</option>)}</Select>}</Field>}
      </div>
    </Modal>
  );
}

export default function DashboardBuilder() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const canWrite = can("dashboard.write");
  const [edit, setEdit] = useState(false);
  const [name, setName] = useState("");
  const [widgets, setWidgets] = useState<any[]>([]);
  const [filters, setFilters] = useState<any>({ range: "this_fy" });
  const [policy, setPolicy] = useState("latest_published");
  const [dirty, setDirty] = useState(false);
  const [tick, setTick] = useState(0);
  const [modal, setModal] = useState<any>(null);
  const area = useRef<HTMLDivElement>(null);
  const store = useRef<Record<string, any>>({});
  const q = useQuery({ queryKey: ["dashboard", id], queryFn: () => api.get(`/dashboards/${id}`) });
  const depts = useQuery({
    queryKey: ["dept-values"],
    queryFn: async () => {
      const list = await api.get("/datasets?status=ready&page_size=20");
      const vals = new Set<string>();
      for (const d of list.items.slice(0, 6)) { const full = await api.get(`/datasets/${d.id}`); full.profile?.columns?.find((c: any) => c.name === "department" || c.name === "business_unit")?.top_values?.forEach((t: any) => vals.add(t.value)); }
      return [...vals];
    },
  });

  useEffect(() => { if (q.data) { setName(q.data.name); setWidgets(q.data.widgets); setFilters(q.data.filters?.range ? q.data.filters : { range: "this_fy", ...q.data.filters }); setPolicy(q.data.version_policy); setDirty(false); } }, [q.data]);

  const save = useMutation({
    mutationFn: () => api.patch(`/dashboards/${id}`, { name, widgets, filters, version_policy: policy }),
    onSuccess: (d) => { toast.success("Dashboard saved"); setDirty(false); qc.setQueryData(["dashboard", id], d); qc.invalidateQueries({ queryKey: ["dashboards"] }); },
    onError: (e: ApiError) => toast.error("Could not save", e.message),
  });
  const report = useCallback((wid: string, d: any) => { store.current[wid] = d; }, []);
  const change = (fn: () => void) => { fn(); setDirty(true); };
  const onLayout = (l: Layout[]) => {
    if (!edit) return;
    setWidgets((ws) => ws.map((w) => { const p = l.find((x) => x.i === w.id); return p && (p.x !== w.x || p.y !== w.y || p.w !== w.w || p.h !== w.h) ? { ...w, x: p.x, y: p.y, w: p.w, h: p.h } : w; }));
    setDirty(true);
  };
  const layouts = useMemo(() => ({ lg: widgets.map((w) => ({ i: w.id, x: w.x ?? 0, y: w.y ?? 0, w: w.w ?? 4, h: w.h ?? 3, minW: 2, minH: 2 })) }), [widgets]);

  const exportPng = async () => {
    if (!area.current) return;
    try { const url = await toPng(area.current, { pixelRatio: 2, backgroundColor: getComputedStyle(document.body).backgroundColor, filter: (n) => !(n as HTMLElement).dataset?.noexport }); const b = await (await fetch(url)).blob(); downloadBlob(b, `${name || "dashboard"}.png`); } catch { toast.error("PNG export failed"); }
  };
  const exportPdf = async () => {
    if (!area.current) return;
    try {
      const url = await toPng(area.current, { pixelRatio: 2, backgroundColor: getComputedStyle(document.body).backgroundColor, filter: (n) => !(n as HTMLElement).dataset?.noexport });
      const img = new Image(); img.src = url; await img.decode();
      const { jsPDF } = await import("jspdf");
      const pdf = new jsPDF({ orientation: img.width > img.height ? "l" : "p", unit: "pt", format: "a4" });
      const pw = pdf.internal.pageSize.getWidth() - 40; const ratio = pw / img.width;
      pdf.setFontSize(14); pdf.text(name || "Dashboard", 20, 28);
      pdf.addImage(url, "PNG", 20, 40, pw, img.height * ratio);
      pdf.save(`${name || "dashboard"}.pdf`);
    } catch { toast.error("PDF export failed"); }
  };
  const exportCsv = () => {
    const rows: any[][] = [];
    widgets.forEach((w) => { const d = store.current[w.id]; if (!d?.ok) return; if (w.type === "kpi") rows.push([d.title, "", d.rows[0]?.[d.rows[0].length - 1]]); else d.rows.forEach((r: any[]) => rows.push([d.title, r[0], r[r.length - 1]])); });
    downloadBlob(new Blob([toCsv(["Widget", "Group", "Value"], rows)], { type: "text/csv" }), `${name || "dashboard"}.csv`);
  };

  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data) return <div className="space-y-4"><Skeleton className="h-10 w-1/3" /><Skeleton className="h-96" /></div>;
  const saveWidget = (w: any) => { change(() => { if (w.id) setWidgets((ws) => ws.map((x) => (x.id === w.id ? { ...x, ...w } : x))); else setWidgets((ws) => [...ws, { ...w, id: `w${Date.now().toString(36)}`, x: 0, y: 999, w: w.type === "kpi" ? 3 : 6, h: w.type === "kpi" ? 2 : 4 }]); }); setModal(null); };

  return (
    <div className="mx-auto max-w-[1500px]">
      <BackLink to="/app/dashboards">Dashboards</BackLink>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {edit ? <Input value={name} onChange={(e) => change(() => setName(e.target.value))} className="h-11 max-w-sm text-lg font-semibold" aria-label="Dashboard name" data-testid="dash-name" /> : <h1 className="text-2xl font-semibold tracking-tight" data-testid="dash-title">{name}</h1>}
        {dirty && <Badge tone="warning">unsaved changes</Badge>}
        <div className="ml-auto flex flex-wrap items-center gap-2" data-noexport="1">
          <Select value={filters.range || "all"} onChange={(e) => change(() => setFilters({ ...filters, range: e.target.value }))} className="w-44" aria-label="Time range" data-testid="dash-range">{RANGES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
          <Select value={filters.department || ""} onChange={(e) => change(() => setFilters({ ...filters, department: e.target.value || undefined }))} className="w-44" aria-label="Department / business unit filter" data-testid="dash-dept"><option value="">All business units</option>{depts.data?.map((d) => <option key={d}>{d}</option>)}</Select>
          <Select value={policy} onChange={(e) => change(() => setPolicy(e.target.value))} disabled={!edit} className="w-48" aria-label="Version policy" title="latest_published (default): widgets follow the live governed definition. pinned: widgets read a specific metric version." data-testid="dash-policy"><option value="latest_published">Latest published</option><option value="pinned">Pinned versions</option></Select>
          <Button variant="outline" size="icon" aria-label="Refresh data" onClick={() => { setTick((t) => t + 1); qc.invalidateQueries({ queryKey: ["widget"] }); }}><RefreshCw className="h-4 w-4" /></Button>
          <Menu><MenuTrigger asChild><Button variant="outline"><Download className="h-4 w-4" />Export</Button></MenuTrigger><MenuContent><MenuItem onSelect={exportPng}><FileImage className="h-4 w-4" />PNG image</MenuItem><MenuItem onSelect={exportPdf}><FileText className="h-4 w-4" />PDF</MenuItem><MenuItem onSelect={exportCsv}><Table2 className="h-4 w-4" />CSV data</MenuItem></MenuContent></Menu>
          {canWrite && <>
            <Button variant={edit ? "accent" : "outline"} onClick={() => setEdit((e) => !e)} data-testid="dash-edit">{edit ? <><Unlock className="h-4 w-4" />Editing</> : <><Pencil className="h-4 w-4" />Edit layout</>}</Button>
            {edit && <Button variant="outline" onClick={() => setModal({ type: "kpi" })} data-testid="add-widget"><Plus className="h-4 w-4" />Add widget</Button>}
            <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!dirty} data-testid="dash-save"><Save className="h-4 w-4" />Save</Button>
          </>}
        </div>
      </div>
      {policy === "pinned" && <p className="mb-3 flex items-center gap-2 text-xs text-muted-foreground"><Lock className="h-3.5 w-3.5" />Pinned mode: each widget reads the metric version you chose, so published changes won't alter this dashboard.</p>}
      <div ref={area} className="rounded-2xl bg-background p-1">
        {widgets.length === 0 ? <div className="card py-20 text-center text-muted-foreground">No widgets yet. {canWrite ? "Click Edit layout, then Add widget." : ""}</div> : (
          <Grid className="layout" layouts={layouts} breakpoints={{ lg: 996, sm: 0 }} cols={{ lg: 12, sm: 1 }} rowHeight={56} margin={[14, 14]} isDraggable={edit} isResizable={edit} draggableHandle=".drag-handle" onLayoutChange={onLayout} compactType="vertical">
            {widgets.map((w) => (
              <div key={w.id} className="card flex flex-col overflow-hidden p-4" data-testid="widget">
                <div className="mb-2 flex items-center gap-2">
                  {edit && <span className="drag-handle cursor-grab text-muted-foreground active:cursor-grabbing" aria-label="Drag to move" data-noexport="1"><GripVertical className="h-4 w-4" /></span>}
                  <h3 className="min-w-0 flex-1 truncate text-sm font-semibold">{w.title}</h3>
                  {w.pinned_version && <Badge tone="outline" className="font-mono">v{w.pinned_version}</Badge>}
                  {edit && <span className="flex" data-noexport="1"><button className="rounded p-1 hover:bg-muted" aria-label={`Edit ${w.title}`} onClick={() => setModal(w)}><Pencil className="h-3.5 w-3.5" /></button><button className="rounded p-1 hover:bg-muted" aria-label={`Remove ${w.title}`} onClick={() => change(() => setWidgets((ws) => ws.filter((x) => x.id !== w.id)))}><Trash2 className="h-3.5 w-3.5" /></button></span>}
                </div>
                <div className="min-h-0 flex-1"><WidgetBody w={w} filters={filters} policy={policy} tick={tick} report={report} /></div>
              </div>
            ))}
          </Grid>
        )}
      </div>
      {modal && <WidgetModal open onClose={() => setModal(null)} initial={modal} onSave={saveWidget} policy={policy} />}
    </div>
  );
}
