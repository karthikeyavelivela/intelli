import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import { useEffect, useState } from "react";
import { useDebounced } from "@/components/common";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export interface MetricDraft {
  name: string; description: string; business_definition: string; formula: string; filters: string; unit: string;
  time_window: string; date_column: string; dataset_id: string; department: string; category: string; aggregation?: string;
}
export const EMPTY_DRAFT: MetricDraft = { name: "", description: "", business_definition: "", formula: "", filters: "", unit: "", time_window: "all_time", date_column: "", dataset_id: "", department: "", category: "" };
const DEPTS = ["Sales", "Finance", "Operations", "Marketing", "Product", "Customer Success"];
const WINDOWS = [["all_time", "All time"], ["ytd", "Financial year to date (Apr-Mar)"], ["mtd", "Month to date"], ["last_12_months", "Last 12 months"], ["last_90_days", "Last 90 days"], ["last_30_days", "Last 30 days"]];

export function ValidationPanel({ report, loading }: { report: any; loading?: boolean }) {
  if (loading) return <p className="flex items-center gap-2 text-xs text-muted-foreground"><Spinner className="h-3 w-3" />Validating…</p>;
  if (!report) return null;
  return (
    <div className={`rounded-xl border p-3 text-sm ${report.ok ? "border-success/30 bg-success/5" : "border-danger/30 bg-danger/5"}`} role="status" data-testid="validation-panel" data-ok={report.ok}>
      <p className={`flex items-center gap-2 font-medium ${report.ok ? "text-success" : "text-danger"}`}>{report.ok ? <CheckCircle2 className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}{report.ok ? "Formula is valid" : "Validation failed"}</p>
      {report.errors?.map((e: any, i: number) => <p key={i} className="mt-1 break-words text-danger">{e.message}</p>)}
      {report.warnings?.map((w: string, i: number) => <p key={i} className="mt-1 flex gap-1.5 text-warning"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{w}</p>)}
      {report.ok && (
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-muted-foreground sm:grid-cols-4">
          <div><dt className="font-medium text-foreground">Columns</dt><dd>{report.columns.join(", ") || "—"}</dd></div>
          <div><dt className="font-medium text-foreground">Aggregations</dt><dd>{report.aggregations.join(", ") || "—"}</dd></div>
          <div><dt className="font-medium text-foreground">Metric refs</dt><dd>{report.metrics.join(", ") || "—"}</dd></div>
          <div><dt className="font-medium text-foreground">Returns</dt><dd>{report.result_type}</dd></div>
        </dl>
      )}
    </div>
  );
}

export function MetricForm({ value, onChange, showReason, reason, onReason, onValidation }: {
  value: MetricDraft; onChange: (v: MetricDraft) => void; showReason?: boolean; reason?: string; onReason?: (r: string) => void; onValidation?: (r: any) => void;
}) {
  const { can } = useAuth();
  const datasets = useQuery({ queryKey: ["datasets", "ready"], queryFn: () => api.get("/datasets?status=ready&page_size=100") });
  const ds = useQuery({ queryKey: ["dataset", value.dataset_id], enabled: !!value.dataset_id, queryFn: () => api.get(`/datasets/${value.dataset_id}`) });
  const [report, setReport] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const dv = useDebounced({ f: value.formula, fl: value.filters, d: value.dataset_id, dc: value.date_column, tw: value.time_window }, 600);
  const set = (k: keyof MetricDraft) => (e: React.ChangeEvent<any>) => onChange({ ...value, [k]: e.target.value });

  useEffect(() => {
    if (!dv.f.trim() || !dv.d || !can("formula.run")) { setReport(null); onValidation?.(null); return; }
    let cancel = false;
    setBusy(true);
    api.post("/validation/formula", { dataset_id: dv.d, formula: dv.f, filters: dv.fl || null, date_column: dv.dc || null, time_window: dv.tw })
      .then((r) => { if (!cancel) { setReport(r); onValidation?.(r); } })
      .catch(() => !cancel && setReport(null))
      .finally(() => !cancel && setBusy(false));
    return () => { cancel = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dv.f, dv.fl, dv.d, dv.dc, dv.tw]);

  const dateCols = (ds.data?.schema || []).filter((c: any) => c.category === "date");
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Metric name">{(id) => <Input id={id} value={value.name} onChange={set("name")} placeholder="Revenue" data-testid="mf-name" />}</Field>
        <Field label="Dataset" hint="Where the formula's columns come from.">{(id) => (
          <Select id={id} value={value.dataset_id} onChange={(e) => onChange({ ...value, dataset_id: e.target.value, date_column: "" })} data-testid="mf-dataset">
            <option value="">Select a dataset…</option>
            {datasets.data?.items.map((d: any) => <option key={d.id} value={d.id}>{d.name} ({d.row_count.toLocaleString()} rows)</option>)}
          </Select>
        )}</Field>
      </div>
      <Field label="Description">{(id) => <Textarea id={id} value={value.description} onChange={set("description")} rows={2} placeholder="What does this metric measure?" />}</Field>
      <Field label="Business definition" hint="The plain-language rule everyone agrees on.">{(id) => <Textarea id={id} value={value.business_definition} onChange={set("business_definition")} rows={2} />}</Field>
      <Field label="Formula" hint="Aggregates: SUM, AVG, COUNT, COUNT_DISTINCT, SUMIF… Reference other metrics as [Revenue]. Raw SQL is not accepted.">{(id) => (
        <Textarea id={id} value={value.formula} onChange={set("formula")} rows={3} spellCheck={false} className="font-mono" placeholder="SUM(net_sales) - SUM(refund_amount)" data-testid="mf-formula" />
      )}</Field>
      {ds.data && <p className="text-xs text-muted-foreground">Columns: {ds.data.schema.map((c: any) => <code key={c.name} className="mr-1.5 rounded bg-muted px-1 py-0.5">{c.name}<span className="text-muted-foreground/70"> {c.category}</span></code>)}</p>}
      <ValidationPanel report={report} loading={busy} />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Row filter (optional)" hint="Boolean condition, e.g. region = 'South' AND payment_method = 'UPI'">{(id) => <Input id={id} value={value.filters} onChange={set("filters")} className="font-mono" placeholder="region = 'South'" data-testid="mf-filters" />}</Field>
        <Field label="Unit">{(id) => <Input id={id} value={value.unit} onChange={set("unit")} placeholder="INR, count, percent…" list="units" data-testid="mf-unit" />}</Field>
        <datalist id="units">{["INR", "count", "percent", "days", "ratio"].map((u) => <option key={u} value={u} />)}</datalist>
        <Field label="Time window">{(id) => <Select id={id} value={value.time_window} onChange={set("time_window")}>{WINDOWS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>}</Field>
        <Field label="Date column" hint="Used to apply the time window.">{(id) => <Select id={id} value={value.date_column} onChange={set("date_column")}><option value="">Dataset default</option>{dateCols.map((c: any) => <option key={c.name} value={c.name}>{c.name}</option>)}</Select>}</Field>
        <Field label="Department">{(id) => <Select id={id} value={value.department} onChange={set("department")}><option value="">None</option>{DEPTS.map((d) => <option key={d}>{d}</option>)}</Select>}</Field>
        <Field label="Category">{(id) => <Input id={id} value={value.category} onChange={set("category")} placeholder="Financial, Volume, Quality…" />}</Field>
      </div>
      {showReason && <Field label="Reason for change" hint="Recorded in the immutable version history.">{(id) => <Input id={id} value={reason || ""} onChange={(e) => onReason?.(e.target.value)} placeholder="Why are you changing this?" />}</Field>}
    </div>
  );
}

export function toDraft(m: any): MetricDraft {
  return { ...EMPTY_DRAFT, ...Object.fromEntries(Object.keys(EMPTY_DRAFT).map((k) => [k, m[k] ?? (EMPTY_DRAFT as any)[k]])) } as MetricDraft;
}
export function draftPayload(d: MetricDraft) {
  return { ...d, filters: d.filters || null, unit: d.unit || null, date_column: d.date_column || null, department: d.department || null, category: d.category || null, description: d.description || null, business_definition: d.business_definition || null };
}
