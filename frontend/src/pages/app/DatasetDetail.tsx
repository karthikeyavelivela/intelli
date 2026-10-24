import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BackLink, DataTable, DemoBadge, ErrorState, PageHeader, Pager, TableSkeleton } from "@/components/common";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Progress, Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatBytes, fmtDateTime, ms } from "@/lib/utils";

function Preview({ id }: { id: string }) {
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<{ col: string; desc: boolean } | null>(null);
  const q = useQuery({ queryKey: ["preview", id, page, sort], queryFn: () => api.get(`/datasets/${id}/preview?page=${page}&page_size=15${sort ? `&sort=${sort.col}&desc=${sort.desc}` : ""}`), placeholderData: (p) => p });
  if (q.isError) return <ErrorState error={q.error} />;
  if (!q.data) return <TableSkeleton rows={8} cols={6} />;
  return (
    <>
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">
        {q.data.columns.map((c: string) => <th key={c} className="whitespace-nowrap px-4 py-3 font-medium" aria-sort={sort?.col === c ? (sort.desc ? "descending" : "ascending") : undefined}><button className="uppercase tracking-wider hover:text-foreground" onClick={() => setSort({ col: c, desc: sort?.col === c ? !sort.desc : false })}>{c}{sort?.col === c ? (sort.desc ? " ↓" : " ↑") : ""}</button></th>)}
      </tr></thead><tbody>
        {q.data.rows.map((r: any[], i: number) => <tr key={i} className="border-b last:border-0">{r.map((v, j) => <td key={j} className="whitespace-nowrap px-4 py-2.5 font-mono text-xs">{v === null ? <span className="text-muted-foreground">null</span> : String(v)}</td>)}</tr>)}
      </tbody></table></div>
      <Pager page={page} pageSize={15} total={q.data.total} onPage={setPage} />
    </>
  );
}

export default function DatasetDetail() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const q = useQuery({
    queryKey: ["dataset", id], queryFn: () => api.get(`/datasets/${id}`),
    refetchInterval: (query) => { const s = (query.state.data as any)?.status; return s === "pending" || s === "processing" ? 1200 : false; },
  });
  const jobs = useQuery({ queryKey: ["dataset-jobs", id], queryFn: () => api.get(`/datasets/${id}/jobs`), refetchInterval: q.data?.status === "ready" || q.data?.status === "failed" ? false : 1500 });
  const re = useMutation({ mutationFn: () => api.post(`/datasets/${id}/reprocess`), onSuccess: () => { toast.success("Reprocessing queued"); qc.invalidateQueries({ queryKey: ["dataset", id] }); }, onError: (e: ApiError) => toast.error("Failed", e.message) });

  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;
  const d = q.data;
  if (!d) return <div className="space-y-4"><Skeleton className="h-10 w-1/2" /><Skeleton className="h-80" /></div>;
  const prof = d.profile?.columns || [];
  const busy = d.status === "pending" || d.status === "processing";

  return (
    <div>
      <BackLink to="/app/datasets">Datasets</BackLink>
      <PageHeader
        title={<span className="flex flex-wrap items-center gap-3">{d.name}<StatusBadge status={d.status} />{d.is_demo && <DemoBadge />}</span>}
        description={d.description || d.original_filename}
        actions={can("dataset.write") && d.source_type !== "seed" ? <Button variant="outline" onClick={() => re.mutate()} loading={re.isPending}><RefreshCw className="h-4 w-4" />Reprocess</Button> : undefined}
      />
      {busy && (
        <Card className="mb-4 p-5" role="status" aria-live="polite">
          <div className="mb-2 flex justify-between text-sm"><span className="font-medium capitalize">{d.stage || "queued"}…</span><span className="tabular-nums">{d.progress}%</span></div>
          <Progress value={d.progress} label="Ingestion progress" />
          <p className="mt-2 text-xs text-muted-foreground">Processing in a background worker. You can leave this page; progress is saved.</p>
        </Card>
      )}
      {d.status === "failed" && <div role="alert" className="mb-4 flex items-start gap-3 rounded-2xl border border-danger/30 bg-danger/5 p-4"><AlertTriangle className="mt-0.5 h-5 w-5 text-danger" /><div><p className="font-medium">Ingestion failed</p><p className="text-sm text-muted-foreground">{d.error}</p></div></div>}

      <div className="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-5">
        {[["Rows", d.row_count.toLocaleString()], ["Columns", d.column_count], ["Size (Parquet)", formatBytes(d.size_bytes)], ["Completeness", d.profile?.completeness_pct != null ? `${d.profile.completeness_pct}%` : "—"], ["Duplicate rows", d.profile?.duplicate_rows != null ? `${d.profile.duplicate_rows.toLocaleString()} (${d.profile.duplicate_pct}%)` : "—"]].map(([k, v]) => (
          <Card key={String(k)} className="p-4"><p className="text-xs text-muted-foreground">{k}</p><p className="mt-1 text-xl font-semibold tabular-nums">{v}</p></Card>
        ))}
      </div>

      {d.status === "ready" && (
        <Tabs defaultValue="preview">
          <TabsList><TabsTrigger value="preview">Preview</TabsTrigger><TabsTrigger value="schema">Schema</TabsTrigger><TabsTrigger value="profile">Profiling</TabsTrigger><TabsTrigger value="history">Processing history</TabsTrigger><TabsTrigger value="metrics">Metrics ({d.metrics.length})</TabsTrigger></TabsList>
          <TabsContent value="preview"><Card><Preview id={d.id} /></Card></TabsContent>
          <TabsContent value="schema"><Card><DataTable dense rows={d.schema} rowKey={(c: any) => c.name} columns={[
            { key: "n", header: "Column", cell: (c: any) => <code className="font-medium">{c.name}</code> },
            { key: "t", header: "Detected type", cell: (c: any) => <span className="font-mono text-xs">{c.type}</span> },
            { key: "c", header: "Category", cell: (c: any) => <Badge tone={c.category === "numeric" ? "accent" : "outline"}>{c.category}</Badge> },
            { key: "d", header: "", cell: (c: any) => d.date_column === c.name ? <Badge tone="success">default date column</Badge> : null },
          ]} /></Card></TabsContent>
          <TabsContent value="profile"><Card><DataTable dense rows={prof} rowKey={(c: any) => c.name} columns={[
            { key: "n", header: "Column", cell: (c: any) => <code className="font-medium">{c.name}</code> },
            { key: "nulls", header: "Nulls", cell: (c: any) => <div className="min-w-[110px]"><span className="tabular-nums">{c.nulls.toLocaleString()}</span> <span className="text-xs text-muted-foreground">({c.null_pct}%)</span><Progress value={c.null_pct} className="mt-1 h-1" label={`${c.name} null percentage`} /></div> },
            { key: "dist", header: "Distinct (≈)", cell: (c: any) => <span className="tabular-nums">{c.distinct.toLocaleString()}</span> },
            { key: "min", header: "Min", cell: (c: any) => <span className="font-mono text-xs">{c.min ?? "—"}</span> },
            { key: "max", header: "Max", cell: (c: any) => <span className="font-mono text-xs">{c.max ?? "—"}</span> },
            { key: "mean", header: "Mean", cell: (c: any) => <span className="tabular-nums">{c.mean ?? "—"}</span> },
            { key: "top", header: "Top values", cell: (c: any) => <div className="flex max-w-xs flex-wrap gap-1">{(c.top_values || []).slice(0, 4).map((t: any) => <Badge key={t.value} tone="outline">{t.value} · {t.count.toLocaleString()}</Badge>)}</div> },
          ]} /></Card></TabsContent>
          <TabsContent value="history"><Card><DataTable dense rows={jobs.data?.items || []} rowKey={(j: any) => j.id} columns={[
            { key: "s", header: "Status", cell: (j: any) => <StatusBadge status={j.status} /> },
            { key: "r", header: "Runner", cell: (j: any) => <Badge tone="outline">{j.runner || "—"}</Badge> },
            { key: "rows", header: "Rows", cell: (j: any) => j.rows.toLocaleString() },
            { key: "ms", header: "Duration", cell: (j: any) => ms(j.duration_ms) },
            { key: "at", header: "Finished", cell: (j: any) => fmtDateTime(j.finished_at || j.created_at) },
            { key: "e", header: "Errors", cell: (j: any) => j.error_report?.fatal ? <span className="text-danger">{j.error_report.fatal}</span> : j.error_report?.rejected_rows ? <span className="text-warning">{j.error_report.rejected_rows} rejected rows</span> : <span className="text-muted-foreground">none</span> },
          ]} /></Card></TabsContent>
          <TabsContent value="metrics"><Card><CardBody className="space-y-2 pt-5">
            {d.metrics.length === 0 ? <p className="text-sm text-muted-foreground">No metrics use this dataset yet.</p> : d.metrics.map((m: any) => <Link key={m.id} to={`/app/metrics/${m.id}`} className="flex items-center justify-between rounded-xl border p-3 text-sm hover:bg-muted"><span>{m.name}</span><StatusBadge status={m.status} /></Link>)}
          </CardBody></Card></TabsContent>
        </Tabs>
      )}
      {d.status === "failed" && jobs.data?.items?.[0]?.error_report?.samples && <Card className="mt-4"><CardHeader title="Error report" /><CardBody><DataTable dense rows={jobs.data.items[0].error_report.samples} rowKey={(s: any) => `${s.line}${s.column}`} columns={[{ key: "l", header: "Line", cell: (s: any) => s.line }, { key: "c", header: "Column", cell: (s: any) => s.column }, { key: "e", header: "Error", cell: (s: any) => s.error }]} /></CardBody></Card>}
    </div>
  );
}
