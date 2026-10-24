import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Bot, Send, Sparkles, Wand2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState, PageHeader } from "@/components/common";
import { EMPTY_DRAFT, MetricForm, draftPayload, toDraft, type MetricDraft } from "@/components/MetricForm";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Select, Textarea } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ms, timeAgo } from "@/lib/utils";

const EXAMPLES = [
  "Total net sales for the Online channel",
  "Average quantity per order line",
  "Number of distinct customers who ordered in the South region",
  "Total GST collected",
  "Gross margin percentage",
];

export default function Generator() {
  const { can } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [prompt, setPrompt] = useState("");
  const [dsId, setDsId] = useState("");
  const [result, setResult] = useState<any>(null);
  const [draft, setDraft] = useState<MetricDraft>(EMPTY_DRAFT);
  const [validation, setValidation] = useState<any>(null);
  const status = useQuery({ queryKey: ["ai-status"], queryFn: () => api.get("/ai/status") });
  const datasets = useQuery({ queryKey: ["datasets", "ready"], queryFn: () => api.get("/datasets?status=ready&page_size=100") });
  const history = useQuery({ queryKey: ["generations"], queryFn: () => api.get("/ai/generations?page_size=8") });

  const gen = useMutation({
    mutationFn: () => api.post("/ai/generate-metric", { prompt, dataset_id: dsId }),
    onSuccess: (r) => {
      setResult(r); setValidation(r.validation);
      if (r.suggestion) setDraft(toDraft({ ...r.suggestion, dataset_id: dsId }));
      qc.invalidateQueries({ queryKey: ["generations"] });
    },
    onError: (e: ApiError) => toast.error("TARA could not generate", e.message),
  });
  const save = useMutation({
    mutationFn: (submit: boolean) => api.post(`/ai/generations/${result.id}/save`, { definition: draftPayload(draft), submit }),
    onSuccess: (m, submit) => { toast.success(submit ? "Submitted for approval" : "Saved as draft", `${m.name} is not published until a reviewer approves it.`); qc.invalidateQueries({ queryKey: ["metrics"] }); qc.invalidateQueries({ queryKey: ["generations"] }); nav(`/app/metrics/${m.id}`); },
    onError: (e: ApiError) => toast.error(e.code === "invalid_formula" ? "Fix the formula before submitting" : "Could not save", e.message),
  });
  const canSubmit = can("metric.write") && validation?.ok;

  return (
    <div>
      <PageHeader eyebrow="TARA" title="Metric generator" description="Describe a metric in plain English. TARA grounds the definition in your real dataset schema and existing catalog, then you review, edit and decide. Nothing is ever auto-published or auto-executed." />
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-2xl border bg-card p-3 text-sm" data-testid="ai-mode">
        <Bot className="h-4 w-4 text-accent" />
        {status.data?.enabled ? <><span className="font-medium">TARA is using {status.data.provider} ({status.data.model})</span><Badge tone="success">AI mode</Badge></> : <><span className="font-medium">Offline deterministic mode</span><Badge tone="warning">no AI key configured</Badge><span className="text-muted-foreground">Keyword matching against your schema. Add an AI key in the backend env for richer results.</span></>}
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,420px)_1fr]">
        <div className="space-y-4">
          <Card>
            <CardHeader title="Describe the metric" />
            <CardBody className="space-y-4">
              <Field label="Dataset">{(id) => <Select id={id} value={dsId} onChange={(e) => setDsId(e.target.value)} data-testid="gen-dataset"><option value="">Choose a dataset…</option>{datasets.data?.items.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select>}</Field>
              <Field label="In plain English">{(id) => <Textarea id={id} value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4} placeholder="e.g. Total net sales for the Online channel" data-testid="gen-prompt" />}</Field>
              <div className="flex flex-wrap gap-1.5">{EXAMPLES.map((e) => <button key={e} onClick={() => setPrompt(e)} className="rounded-full border px-2.5 py-1 text-xs hover:bg-muted">{e}</button>)}</div>
              <Button className="w-full" variant="accent" onClick={() => gen.mutate()} loading={gen.isPending} disabled={prompt.trim().length < 8 || !dsId} data-testid="gen-submit"><Wand2 className="h-4 w-4" />Generate with TARA</Button>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Recent generations" />
            <CardBody className="space-y-2">
              {history.data?.items.length ? history.data.items.map((g: any) => (
                <div key={g.id} className="rounded-xl border p-3 text-sm"><div className="flex items-center justify-between gap-2"><span className="truncate font-medium">{g.name || "(no output)"}</span><Badge tone={g.mode === "ai" ? "accent" : "outline"}>{g.mode}</Badge></div><p className="mt-0.5 line-clamp-1 text-xs text-muted-foreground">{g.prompt}</p><p className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">{g.metric_id ? <StatusBadge status={g.status} /> : <span>{g.status}</span>}<span>{ms(g.latency_ms)}</span><span>{timeAgo(g.created_at)}</span></p></div>
              )) : <p className="text-sm text-muted-foreground">No generations yet.</p>}
            </CardBody>
          </Card>
        </div>

        <div>
          {!result ? <EmptyState title="Your suggestion appears here" description="Pick a dataset, describe the metric, and TARA drafts the name, formula, filters and explanation, validated against the real schema." image={IMAGES.features.tara} icon={<Sparkles className="h-6 w-6" />} /> : !result.ok ? (
            <Card className="p-6" role="alert"><p className="flex items-center gap-2 font-medium"><AlertTriangle className="h-5 w-5 text-warning" />TARA couldn't map that request</p><p className="mt-2 text-sm text-muted-foreground">{result.error}</p></Card>
          ) : (
            <Card data-testid="gen-result">
              <CardHeader title={draft.name || "Suggestion"} description={result.label} action={<Badge tone={result.mode === "ai" ? "accent" : "warning"}>{result.mode === "ai" ? `TARA · ${result.provider}` : "offline mode"}</Badge>} />
              <CardBody className="space-y-4">
                {result.notice && <p className="flex items-start gap-2 rounded-xl border border-warning/40 bg-warning/10 p-3 text-sm" role="status"><AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warning" />{result.notice}</p>}
                {result.suggestion.explanation && <div className="rounded-xl bg-muted/60 p-3 text-sm"><p className="font-medium">TARA's explanation</p><p className="mt-1 text-muted-foreground">{result.suggestion.explanation}</p>{result.suggestion.assumptions?.length > 0 && <ul className="mt-2 list-disc space-y-0.5 pl-5 text-xs text-muted-foreground">{result.suggestion.assumptions.map((a: string, i: number) => <li key={i}>{a}</li>)}</ul>}</div>}
                <MetricForm value={draft} onChange={setDraft} onValidation={setValidation} />
                <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
                  <Button variant="ghost" onClick={async () => { await api.post(`/ai/generations/${result.id}/discard`); setResult(null); toast.success("Suggestion discarded"); }}>Discard</Button>
                  <Button variant="outline" onClick={() => save.mutate(false)} loading={save.isPending && save.variables === false} disabled={!can("metric.write") || !draft.name || !draft.formula} data-testid="gen-save">Save as draft</Button>
                  <Button onClick={() => save.mutate(true)} loading={save.isPending && save.variables === true} disabled={!canSubmit} title={!validation?.ok ? "Fix validation errors first" : undefined} data-testid="gen-submit-review"><Send className="h-4 w-4" />Submit for approval</Button>
                </div>
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
