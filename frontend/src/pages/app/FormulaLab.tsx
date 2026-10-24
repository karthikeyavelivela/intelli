import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Clock, Download, Play, ScanLine, ShieldCheck, Timer } from "lucide-react";
import { useState } from "react";
import { SeriesChart } from "@/components/charts";
import { CodeBlock, DataTable, PageHeader, Pager } from "@/components/common";
import { ValidationPanel } from "@/components/MetricForm";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { downloadBlob, formatValue, ms, timeAgo, toCsv } from "@/lib/utils";

const SAMPLES = [
  ["Net revenue", "SUM(net_sales)"],
  ["Revenue less refunds", "[Revenue] - SUM(refund_amount)"],
  ["Refund rate", "COUNTIF(refund_amount > 0) / COUNT(*) * 100"],
  ["Margin %", "(SUM(net_sales) - SUM(cost)) / SUM(net_sales) * 100"],
  ["UPI share of revenue %", "SUMIF(net_sales, payment_method = 'UPI') / SUM(net_sales) * 100"],
  ["GST collected", "SUM(gst_amount)"],
  ["COD return rate %", "COUNTIF(refund_amount > 0 AND payment_method = 'COD') / COUNTIF(payment_method = 'COD') * 100"],
];

export default function FormulaLab() {
  const toast = useToast();
  const qc = useQueryClient();
  const [dsId, setDsId] = useState("");
  const [formula, setFormula] = useState("SUM(net_sales)");
  const [filters, setFilters] = useState("");
  const [dim, setDim] = useState("");
  const [grain, setGrain] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [order, setOrder] = useState("dim");
  const [limit, setLimit] = useState(500);
  const [report, setReport] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<{ message: string; position?: number } | null>(null);
  const [hp, setHp] = useState(1);
  const datasets = useQuery({ queryKey: ["datasets", "ready"], queryFn: () => api.get("/datasets?status=ready&page_size=100") });
  const ds = useQuery({ queryKey: ["dataset", dsId], enabled: !!dsId, queryFn: () => api.get(`/datasets/${dsId}`) });
  const metrics = useQuery({ queryKey: ["live-metrics"], queryFn: () => api.get("/metrics?live_only=true&page_size=50") });
  const history = useQuery({ queryKey: ["exec-history", hp], queryFn: () => api.get(`/execution/history?page=${hp}&page_size=8`) });
  const cols = ds.data?.schema || [];
  const dateCols = cols.filter((c: any) => c.category === "date");

  const validate = useMutation({
    mutationFn: () => api.post("/validation/formula", { dataset_id: dsId, formula, filters: filters || null }),
    onSuccess: (r) => { setReport(r); setError(null); qc.invalidateQueries({ queryKey: ["exec-history"] }); },
    onError: (e: ApiError) => toast.error("Validation failed", e.message),
  });
  const run = useMutation({
    mutationFn: () => api.post("/execution/run", {
      dataset_id: dsId, formula, filters: filters || null, order, limit,
      dimensions: dim ? [{ column: dim, ...(grain ? { grain } : {}) }] : [],
      time_range: start || end ? { column: ds.data?.date_column, start: start || null, end: end || null } : null,
    }),
    onSuccess: (r) => { setResult(r); setError(null); setReport(null); qc.invalidateQueries({ queryKey: ["exec-history"] }); },
    onError: (e: ApiError) => { setResult(null); setError({ message: e.message, position: e.details?.[0]?.position }); qc.invalidateQueries({ queryKey: ["exec-history"] }); },
  });
  const chart = result && dim && result.rows.length > 0 && typeof result.rows[0][result.rows[0].length - 1] === "number"
    ? result.rows.map((r: any[]) => ({ x: String(r[0]), y: r[r.length - 1] })) : null;

  return (
    <div>
      <PageHeader eyebrow="Safe execution" title="Formula Lab" description="Write an expression in the restricted grammar. It is parsed to an AST, validated against the schema and compiled to parameterized, read-only DuckDB SQL with a timeout and row limit. Raw SQL is never executed." />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,460px)_1fr]">
        <Card>
          <CardHeader title="Expression" />
          <CardBody className="space-y-4">
            <Field label="Dataset">{(id) => <Select id={id} value={dsId} onChange={(e) => { setDsId(e.target.value); setReport(null); setResult(null); setDim(""); }} data-testid="lab-dataset"><option value="">Select a dataset…</option>{datasets.data?.items.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select>}</Field>
            <Field label="Formula">{(id) => <Textarea id={id} value={formula} onChange={(e) => setFormula(e.target.value)} rows={4} spellCheck={false} className="font-mono" data-testid="lab-formula" aria-invalid={!!error} />}</Field>
            <div className="flex flex-wrap gap-1.5">{SAMPLES.map(([l, f]) => <button key={l} onClick={() => setFormula(f)} className="rounded-full border px-2.5 py-1 text-xs hover:bg-muted">{l}</button>)}</div>
            {metrics.data?.items.length > 0 && <div><p className="mb-1.5 text-xs font-medium text-muted-foreground">Insert published metric</p><div className="flex flex-wrap gap-1.5">{metrics.data.items.filter((m: any) => !ds.data || m.dataset_id === ds.data.id).map((m: any) => <button key={m.id} onClick={() => setFormula((f) => `${f}${f && !f.endsWith(" ") ? " " : ""}[${m.name}]`)} className="rounded-full border border-accent/30 bg-accent/5 px-2.5 py-1 text-xs text-accent hover:bg-accent/10">[{m.name}]</button>)}</div></div>}
            {cols.length > 0 && <div><p className="mb-1.5 text-xs font-medium text-muted-foreground">Columns (click to insert)</p><div className="flex flex-wrap gap-1.5">{cols.map((c: any) => <button key={c.name} title={c.category} onClick={() => setFormula((f) => f + c.name)} className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[11px] hover:bg-accent/10">{c.name}</button>)}</div></div>}
            <Field label="Row filter (optional)" hint="Boolean condition, e.g. region = 'South' AND channel <> 'Store'">{(id) => <Input id={id} value={filters} onChange={(e) => setFilters(e.target.value)} className="font-mono" />}</Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Group by">{(id) => <Select id={id} value={dim} onChange={(e) => { setDim(e.target.value); setGrain(""); }} data-testid="lab-dim"><option value="">None (single value)</option>{cols.filter((c: any) => c.category !== "numeric").map((c: any) => <option key={c.name}>{c.name}</option>)}</Select>}</Field>
              <Field label="Time grain">{(id) => <Select id={id} value={grain} onChange={(e) => setGrain(e.target.value)} disabled={!dateCols.some((c: any) => c.name === dim)} data-testid="lab-grain"><option value="">—</option>{["day", "week", "month", "quarter", "year"].map((g) => <option key={g}>{g}</option>)}</Select>}</Field>
              <Field label="From">{(id) => <Input id={id} type="date" value={start} onChange={(e) => setStart(e.target.value)} />}</Field>
              <Field label="To">{(id) => <Input id={id} type="date" value={end} onChange={(e) => setEnd(e.target.value)} />}</Field>
              <Field label="Order">{(id) => <Select id={id} value={order} onChange={(e) => setOrder(e.target.value)}><option value="dim">By group</option><option value="value_desc">Value, high to low</option><option value="value_asc">Value, low to high</option></Select>}</Field>
              <Field label="Row limit">{(id) => <Input id={id} type="number" min={1} max={10000} value={limit} onChange={(e) => setLimit(Number(e.target.value))} />}</Field>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" className="flex-1" onClick={() => validate.mutate()} loading={validate.isPending} disabled={!dsId || !formula.trim()} data-testid="lab-validate"><ShieldCheck className="h-4 w-4" />Validate</Button>
              <Button variant="accent" className="flex-1" onClick={() => run.mutate()} loading={run.isPending} disabled={!dsId || !formula.trim()} data-testid="lab-run"><Play className="h-4 w-4" />Execute</Button>
            </div>
          </CardBody>
        </Card>

        <div className="space-y-4">
          {report && <ValidationPanel report={report} />}
          {error && <Card className="border-danger/40 p-5" role="alert" data-testid="lab-error"><p className="font-medium text-danger">Query rejected</p><p className="mt-1 text-sm">{error.message}</p>{error.position !== undefined && <CodeBlock className="mt-3">{formula}{"\n"}{" ".repeat(Math.min(error.position, 300))}^</CodeBlock>}<p className="mt-2 text-xs text-muted-foreground">Nothing was executed against the database.</p></Card>}
          {result && (
            <Card data-testid="lab-result">
              <CardHeader title="Result" action={<Button size="sm" variant="outline" onClick={() => downloadBlob(new Blob([toCsv(result.columns, result.rows)], { type: "text/csv" }), "formula-result.csv")}><Download className="h-4 w-4" />CSV</Button>} />
              <CardBody className="space-y-4">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[[Timer, "Duration", ms(result.duration_ms)], [ScanLine, "Rows scanned", result.scanned_rows.toLocaleString()], [Clock, "Rows returned", `${result.row_count}${result.truncated ? "+" : ""}`], [ShieldCheck, "Limits", `${result.timeout_s}s · ${result.row_limit} rows`]].map(([I, k, v]: any) => <div key={k} className="rounded-xl border p-3"><p className="flex items-center gap-1.5 text-xs text-muted-foreground"><I className="h-3.5 w-3.5" />{k}</p><p className="mt-1 font-semibold tabular-nums">{v}</p></div>)}
                </div>
                {!dim && result.rows.length === 1 && <p className="display text-5xl tabular-nums" data-testid="lab-value">{formatValue(result.rows[0][0])}</p>}
                {chart && <SeriesChart type={grain ? "line" : "bar"} data={chart} name="Value" />}
                {(dim || result.rows.length !== 1) && <div className="max-h-80 overflow-auto rounded-xl border"><DataTable dense rows={result.rows.map((r: any, i: number) => ({ r, i }))} rowKey={(x: any) => String(x.i)} columns={result.columns.map((c: string, j: number) => ({ key: c, header: c, cell: (x: any) => <span className="font-mono text-xs">{x.r[j] === null ? "null" : typeof x.r[j] === "number" ? formatValue(x.r[j]) : String(x.r[j])}</span> }))} /></div>}
                {result.metrics_used?.length > 0 && <p className="text-xs text-muted-foreground">Metrics inlined: {result.metrics_used.map((m: string) => <Badge key={m} tone="accent" className="mr-1">[{m}]</Badge>)}</p>}
                <details className="text-xs"><summary className="cursor-pointer text-muted-foreground">Compiled parameterized SQL</summary><CodeBlock className="mt-2">{result.sql}{"\n\n-- params: "}{JSON.stringify(result.params)}</CodeBlock></details>
              </CardBody>
            </Card>
          )}
          <Card>
            <CardHeader title="Execution history" description="Every validation and execution, including rejected ones" />
            <DataTable dense rows={history.data?.items || []} rowKey={(h: any) => h.id}
              columns={[
                { key: "k", header: "Kind", cell: (h: any) => <Badge tone="outline">{h.kind}</Badge> },
                { key: "e", header: "Expression", cell: (h: any) => <button className="max-w-[260px] truncate text-left font-mono text-xs hover:text-accent" onClick={() => h.expression && setFormula(h.expression)} title="Load into editor">{h.expression}</button> },
                { key: "s", header: "Result", cell: (h: any) => h.ok ? <Badge tone="success">ok</Badge> : <span className="text-xs text-danger" title={h.error}>{(h.error || "failed").slice(0, 40)}</span> },
                { key: "d", header: "Time", cell: (h: any) => ms(h.duration_ms) },
                { key: "r", header: "Rows", cell: (h: any) => h.scanned_rows ? h.scanned_rows.toLocaleString() : "—" },
                { key: "t", header: "When", cell: (h: any) => <span className="text-muted-foreground">{timeAgo(h.created_at)}</span> },
              ]} />
            <Pager page={hp} pageSize={8} total={history.data?.total || 0} onPage={setHp} />
          </Card>
        </div>
      </div>
    </div>
  );
}
