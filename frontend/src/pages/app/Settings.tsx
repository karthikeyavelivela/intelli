import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Palette, Server } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/common";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input, Select } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { useTheme } from "@/lib/theme";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { ms } from "@/lib/utils";

export default function Settings() {
  const { can } = useAuth();
  const { setTheme } = useTheme();
  const qc = useQueryClient();
  const toast = useToast();
  const admin = can("workspace.manage");
  const q = useQuery({ queryKey: ["settings"], queryFn: () => api.get("/workspaces/current/settings") });
  const usage = useQuery({ queryKey: ["api-usage"], queryFn: () => api.get("/admin/api-usage"), enabled: admin });
  const [s, setS] = useState<any>({ ai_provider: "", default_theme: "system", data_retention_days: 365 });
  useEffect(() => { if (q.data) setS({ ...q.data.settings, ai_provider: q.data.settings.ai_provider || "" }); }, [q.data]);
  const save = useMutation({
    mutationFn: () => api.put("/workspaces/current/settings", { ai_provider: s.ai_provider || undefined, default_theme: s.default_theme, data_retention_days: Number(s.data_retention_days) }),
    onSuccess: () => { toast.success("Settings saved"); qc.invalidateQueries({ queryKey: ["settings"] }); qc.invalidateQueries({ queryKey: ["ai-status"] }); qc.invalidateQueries({ queryKey: ["api-usage"] }); },
    onError: (e: ApiError) => toast.error("Could not save", e.message),
  });
  const ai = q.data?.ai;
  return (
    <div className="space-y-4">
      <PageHeader title="Settings" description="Appearance for you; AI provider, retention and usage for the workspace." />
      <Card><CardHeader title={<span className="flex items-center gap-2"><Palette className="h-4 w-4" />Appearance</span>} description="Saved in this browser and applied before first paint." /><CardBody><ThemeToggle /></CardBody></Card>
      <Card><CardHeader title={<span className="flex items-center gap-2"><Bot className="h-4 w-4" />TARA &amp; AI provider</span>} description="API keys live only in backend environment variables. They are never sent to or stored in the browser." />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 rounded-xl border bg-muted/50 p-3 text-sm" data-testid="ai-status">{ai?.enabled ? <><Badge tone="success">AI active</Badge><span>{ai.provider} · {ai.model}</span></> : <><Badge tone="warning">Offline mode</Badge><span className="text-muted-foreground">No provider key found in the backend environment; TARA uses deterministic rules and labels its output accordingly.</span></>}</div>
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Provider" hint="Takes effect only if the matching key is set on the server.">{(id) => <Select id={id} value={s.ai_provider} onChange={(e) => setS({ ...s, ai_provider: e.target.value })} disabled={!admin}><option value="">Server default ({ai?.configured_provider || "none"})</option><option value="openai">OpenAI</option><option value="gemini">Gemini</option><option value="none">Disabled (offline)</option></Select>}</Field>
            <Field label="Default theme for new users">{(id) => <Select id={id} value={s.default_theme} onChange={(e) => setS({ ...s, default_theme: e.target.value })} disabled={!admin}><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></Select>}</Field>
            <Field label="Data retention (days)" hint="Audit and execution history older than this may be pruned.">{(id) => <Input id={id} type="number" min={7} max={3650} value={s.data_retention_days} onChange={(e) => setS({ ...s, data_retention_days: e.target.value })} disabled={!admin} />}</Field>
          </div>
          {admin ? <Button onClick={() => { save.mutate(); if (s.default_theme) setTheme(s.default_theme); }} loading={save.isPending}>Save workspace settings</Button> : <p className="text-xs text-muted-foreground">Only admins can change workspace settings.</p>}
        </CardBody></Card>
      {admin && usage.data && (
        <Card><CardHeader title={<span className="flex items-center gap-2"><Server className="h-4 w-4" />API usage</span>} description="AI calls made by this workspace" />
          <CardBody className="space-y-4">
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[["Calls", usage.data.total_calls], ["Succeeded", usage.data.success], ["Failed", usage.data.failed], ["Avg latency", ms(usage.data.avg_latency_ms)]].map(([k, v]) => <div key={String(k)} className="rounded-xl border p-3"><p className="text-xs text-muted-foreground">{k}</p><p className="mt-1 text-xl font-semibold tabular-nums">{v}</p></div>)}</div>
            {usage.data.by_kind.length > 0 ? <div className="flex flex-wrap gap-2">{usage.data.by_kind.map((k: any) => <Badge key={k.kind} tone="outline">{k.kind}: {k.calls}</Badge>)}</div> : <p className="text-sm text-muted-foreground">No AI calls yet. In offline mode TARA never calls an external service.</p>}
          </CardBody></Card>
      )}
      {q.data?.env && <Card><CardHeader title="Runtime limits" /><CardBody><dl className="grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-4"><dt className="text-muted-foreground">Query timeout</dt><dd>{q.data.env.query_timeout_s}s</dd><dt className="text-muted-foreground">Row limit</dt><dd>{q.data.env.query_row_limit.toLocaleString()}</dd><dt className="text-muted-foreground">Max upload</dt><dd>{q.data.env.max_upload_mb} MB</dd><dt className="text-muted-foreground">Job runner</dt><dd>{q.data.env.celery ? "Celery + Redis" : "In-process thread"}</dd></dl></CardBody></Card>}
    </div>
  );
}
