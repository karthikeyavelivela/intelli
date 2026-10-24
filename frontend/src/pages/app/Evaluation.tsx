import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, FlaskConical, Play, X } from "lucide-react";
import { DataTable, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { MultiBar, TrendLines } from "@/components/charts";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDateTime, ms, pct } from "@/lib/utils";

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return <Card className="p-4"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-2xl font-semibold tabular-nums">{value}</p>{sub && <p className="mt-0.5 text-xs text-muted-foreground">{sub}</p>}</Card>;
}

export default function Evaluation() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const latest = useQuery({ queryKey: ["eval-latest"], queryFn: () => api.get("/evaluation/latest") });
  const runs = useQuery({ queryKey: ["eval-runs"], queryFn: () => api.get("/evaluation/runs") });
  const run = useMutation({
    mutationFn: () => api.post("/evaluation/run"),
    onSuccess: () => { toast.success("Evaluation complete", "Results computed from live telemetry and stored."); qc.invalidateQueries({ queryKey: ["eval-latest"] }); qc.invalidateQueries({ queryKey: ["eval-runs"] }); },
    onError: (e: ApiError) => toast.error("Evaluation failed", e.message),
  });
  const r = latest.data?.run?.results;
  const header = <PageHeader eyebrow="Performance" title="Evaluation" description="Measured, not claimed. Each run computes processing time, query latency, validation and success rates, conflict-detection precision/recall on labelled ground truth, AI acceptance and dashboard load time, then stores the result."
    actions={can("evaluation.run") && <Button variant="accent" onClick={() => run.mutate()} loading={run.isPending} data-testid="run-eval"><Play className="h-4 w-4" />Run evaluation</Button>} />;
  if (latest.isError) return <ErrorState error={latest.error} />;
  if (latest.isLoading) return <div>{header}<Skeleton className="h-96" /></div>;
  if (!r) return <div>{header}<EmptyState title="No evaluation has been run yet" description={can("evaluation.run") ? "Run an evaluation to measure the platform on your workspace." : "Ask a Data Analyst or Admin to run an evaluation."} image={IMAGES.features.reports} icon={<FlaskConical className="h-6 w-6" />} /></div>;
  const ca = r.conflict_detection;
  const prf = [{ name: "Precision", auto: ca.automated.precision, manual: ca.naive_manual.precision }, { name: "Recall", auto: ca.automated.recall, manual: ca.naive_manual.recall }, { name: "F1", auto: ca.automated.f1, manual: ca.naive_manual.f1 }, { name: "Exact match", auto: ca.automated_exact_match, manual: ca.naive_exact_match }];
  const trend = (runs.data?.items || []).map((x: any, i: number) => ({ name: `#${i + 1}`, precision: x.precision, recall: x.recall, validation: x.validation_pass_rate ?? 0, success: x.query_success_rate ?? 0 }));
  const cc = r.creation_comparison, dc = r.detection_comparison;

  return (
    <div>
      {header}
      <p className="mb-4 text-xs text-muted-foreground">Latest run: {fmtDateTime(latest.data.run.created_at)} · computed in {ms(latest.data.run.duration_ms)}</p>
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Dataset processing (avg)" value={ms(r.dataset_processing.avg_ms)} sub={`${r.dataset_processing.jobs} jobs · ${r.dataset_processing.rows_per_second?.toLocaleString() ?? "—"} rows/s`} />
        <Stat label="Query latency (benchmark avg)" value={ms(r.query_latency.benchmark_avg_ms)} sub={`p95 ${ms(r.query_latency.benchmark_p95_ms)} · ${r.query_latency.benchmark_queries} metrics`} />
        <Stat label="Validation pass rate" value={pct(r.validation.pass_rate)} sub={`${r.validation.metrics_passing}/${r.validation.metrics_checked} metrics`} />
        <Stat label="Query success rate" value={pct(r.query_success.success_rate, 1)} sub={`${r.query_success.ok}/${r.query_success.total} executions`} />
        <Stat label="Conflict precision" value={pct(ca.automated.precision)} sub={`${ca.cases} labelled cases`} />
        <Stat label="Conflict recall" value={pct(ca.automated.recall)} sub={`TP ${ca.automated.tp} · FP ${ca.automated.fp} · FN ${ca.automated.fn}`} />
        <Stat label="AI suggestion acceptance" value={pct(r.ai_acceptance.acceptance_rate)} sub={`${r.ai_acceptance.accepted}/${r.ai_acceptance.generations} accepted · ${pct(r.ai_acceptance.validity_rate)} valid`} />
        <Stat label="Dashboard load (avg)" value={ms(r.dashboard_load.avg_ms)} sub={`${r.dashboard_load.dashboards} dashboards · p95 ${ms(r.dashboard_load.p95_ms)}`} />
      </div>

      <Tabs defaultValue="detect" className="mt-6">
        <TabsList><TabsTrigger value="detect">Conflict detection</TabsTrigger><TabsTrigger value="compare">Manual vs automated</TabsTrigger><TabsTrigger value="perf">Performance</TabsTrigger><TabsTrigger value="trend">Run history</TabsTrigger></TabsList>
        <TabsContent value="detect" className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <Card><CardHeader title="Automated vs manual text diff" description="Scored against labelled ground truth" /><CardBody><MultiBar data={prf} keys={[{ key: "auto", label: "Automated (AST-normalised)" }, { key: "manual", label: "Manual text diff" }]} /></CardBody></Card>
            <Card><CardHeader title="Why the manual diff loses" /><CardBody className="space-y-2 text-sm text-muted-foreground"><p>A plain text comparison flags harmless differences (casing, whitespace, reordered operands, the same filter written in a different place) as conflicts, so its <b className="text-foreground">precision</b> drops to {pct(ca.naive_manual.precision)}.</p><p>The automated check parses both definitions, normalises the AST and compares aggregation, filters, unit, window and dataset separately: precision {pct(ca.automated.precision)}, recall {pct(ca.automated.recall)}.</p></CardBody></Card>
          </div>
          <Card><CardHeader title="Ground-truth cases" description="Expected conflict types vs what each method reported" />
            <DataTable dense rows={ca.rows} rowKey={(x: any) => x.id} columns={[
              { key: "id", header: "Case", cell: (x: any) => <span className="font-mono text-xs">{x.id}</span> },
              { key: "d", header: "Scenario", cell: (x: any) => x.description },
              { key: "e", header: "Expected", cell: (x: any) => <div className="flex flex-wrap gap-1">{x.expected.length ? x.expected.map((t: string) => <Badge key={t} tone="outline">{t}</Badge>) : <span className="text-xs text-muted-foreground">none</span>}</div> },
              { key: "a", header: "Automated", cell: (x: any) => x.automated_correct ? <Check className="h-4 w-4 text-success" aria-label="correct" /> : <span className="flex items-center gap-1 text-danger"><X className="h-4 w-4" />{x.automated.join(", ") || "none"}</span> },
              { key: "n", header: "Manual diff", cell: (x: any) => x.naive_correct ? <Check className="h-4 w-4 text-success" aria-label="correct" /> : <span className="flex items-center gap-1 text-danger"><X className="h-4 w-4" />{x.naive.join(", ") || "none"}</span> },
            ]} /></Card>
        </TabsContent>
        <TabsContent value="compare" className="grid gap-4 md:grid-cols-2">
          <Card><CardHeader title="Metric creation: manual vs AI-assisted" /><CardBody className="space-y-3 text-sm">
            <div className="flex justify-between"><span>Manual (reference assumption)</span><b>{cc.manual_seconds_per_metric_assumed}s</b></div>
            <div className="flex justify-between"><span>TARA generation (measured avg)</span><b>{cc.ai_generation_avg_seconds_measured ?? "—"}s</b></div>
            <div className="flex justify-between"><span>AI-assisted incl. {cc.review_edit_seconds_assumed}s human review (assumed)</span><b>{cc.ai_assisted_total_seconds_est ?? "—"}s</b></div>
            <div className="flex justify-between border-t pt-3"><span>Estimated time saved</span><b className="text-success">{cc.time_saved_pct != null ? `${cc.time_saved_pct}%` : "run a TARA generation first"}</b></div>
            <p className="text-xs text-muted-foreground">{cc.tara_created_metrics} TARA-created metrics in this workspace, {cc.tara_created_valid} currently valid. Manual and review times are stated assumptions; the generation latency is measured.</p></CardBody></Card>
          <Card><CardHeader title="Conflict detection: manual vs automated" /><CardBody className="space-y-3 text-sm">
            <div className="flex justify-between"><span>Candidate definition pairs</span><b>{dc.candidate_pairs}</b></div>
            <div className="flex justify-between"><span>Manual review (assumed {r.assumptions.manual_pair_review_seconds}s / pair)</span><b>{dc.manual_seconds_assumed}s</b></div>
            <div className="flex justify-between"><span>Automated (measured)</span><b>{ms(dc.automated_ms_measured)}</b></div>
            <div className="flex justify-between border-t pt-3"><span>Precision / recall: automated</span><b>{pct(dc.automated_precision)} / {pct(dc.automated_recall)}</b></div>
            <div className="flex justify-between"><span>Precision / recall: manual text diff</span><b>{pct(dc.manual_text_diff_precision)} / {pct(dc.manual_text_diff_recall)}</b></div></CardBody></Card>
        </TabsContent>
        <TabsContent value="perf" className="grid gap-4 md:grid-cols-2">
          <Card><CardHeader title="Query latency per live metric" description="Fresh benchmark on the full dataset" /><DataTable dense rows={r.query_latency.benchmark} rowKey={(b: any) => b.metric} columns={[{ key: "m", header: "Metric", cell: (b: any) => b.metric }, { key: "ms", header: "Latency", cell: (b: any) => ms(b.ms) }, { key: "ok", header: "", cell: (b: any) => b.ok ? <Badge tone="success">ok</Badge> : <Badge tone="danger">failed</Badge> }]} /></Card>
          <Card><CardHeader title="Dashboard load time" /><DataTable dense rows={r.dashboard_load.items} rowKey={(b: any) => b.dashboard} columns={[{ key: "m", header: "Dashboard", cell: (b: any) => b.dashboard }, { key: "w", header: "Widgets", cell: (b: any) => b.widgets }, { key: "ms", header: "Load", cell: (b: any) => ms(b.ms) }, { key: "f", header: "Failed", cell: (b: any) => b.failed_widgets }]} /></Card>
          <Card className="md:col-span-2"><CardHeader title="Dataset processing" /><DataTable dense rows={r.dataset_processing.per_dataset} rowKey={(b: any, ) => b.dataset + b.ms} columns={[{ key: "d", header: "Dataset", cell: (b: any) => b.dataset }, { key: "r", header: "Rows", cell: (b: any) => b.rows.toLocaleString() }, { key: "ms", header: "Duration", cell: (b: any) => ms(b.ms) }, { key: "run", header: "Runner", cell: (b: any) => <Badge tone="outline">{b.runner}</Badge> }]} /></Card>
        </TabsContent>
        <TabsContent value="trend"><Card><CardHeader title="Quality over runs" description="Each point is a stored evaluation run" /><CardBody>{trend.length < 2 ? <p className="py-10 text-center text-sm text-muted-foreground">Run the evaluation again to start a trend line.</p> : <TrendLines percent data={trend} keys={[{ key: "precision", label: "Precision" }, { key: "recall", label: "Recall" }, { key: "validation", label: "Validation pass" }, { key: "success", label: "Query success" }]} />}</CardBody></Card></TabsContent>
      </Tabs>
    </div>
  );
}
