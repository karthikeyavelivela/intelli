import { Download, FileSpreadsheet, FileText, Table2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PageHeader } from "@/components/common";
import { SafeImage } from "@/components/SafeImage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Select } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { downloadBlob } from "@/lib/utils";

const FORMATS = [["csv", "CSV", Table2], ["xlsx", "Excel", FileSpreadsheet], ["pdf", "PDF", FileText]] as const;

export default function Reports() {
  const { user } = useAuth();
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const [dash, setDash] = useState("");
  const dashboards = useQuery({ queryKey: ["dashboards"], queryFn: () => api.get("/dashboards") });
  const download = async (kind: string, fmt: string, extra = "") => {
    const key = `${kind}-${fmt}`;
    setBusy(key);
    try {
      const { blob, filename } = await api.blob(`/reports/${kind}?format=${fmt}${extra}`);
      downloadBlob(blob, filename);
      toast.success("Export ready", filename);
    } catch (e) { toast.error("Export failed", e instanceof ApiError ? e.message : "Unknown error"); }
    finally { setBusy(null); }
  };
  const reports = [
    { kind: "metrics", title: "Metrics catalog", text: "Every metric with status, owner, formula, filters, dataset and version.", img: IMAGES.features.metrics },
    { kind: "conflicts", title: "Conflicts", text: "Detected conflicts with severity, differences, recommendation and resolution.", img: IMAGES.features.conflicts },
    ...(user?.role !== "business_user" ? [{ kind: "evaluation", title: "Evaluation results", text: "Latest performance evaluation: latency, success rates, precision and recall.", img: IMAGES.features.reports }] : []),
  ];
  const Buttons = ({ kind, extra, disabled }: { kind: string; extra?: string; disabled?: boolean }) => (
    <div className="flex flex-wrap gap-2">{FORMATS.map(([f, label, I]) => <Button key={f} size="sm" variant="outline" disabled={disabled} loading={busy === `${kind}-${f}`} onClick={() => download(kind, f, extra)} data-testid={`export-${kind}-${f}`}><I className="h-4 w-4" />{label}</Button>)}</div>
  );
  return (
    <div>
      <PageHeader title="Reports & exports" description="Export governed data to CSV, Excel or PDF. Every export is audit-logged." />
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {reports.map((r) => (
          <Card key={r.kind} hover className="overflow-hidden"><SafeImage image={r.img} className="h-32" /><div className="p-5"><h3 className="font-semibold">{r.title}</h3><p className="mb-4 mt-1 min-h-[2.5rem] text-sm text-muted-foreground">{r.text}</p><Buttons kind={r.kind} /></div></Card>
        ))}
        <Card hover className="overflow-hidden"><SafeImage image={IMAGES.features.dashboards} className="h-32" /><div className="p-5"><h3 className="font-semibold">Dashboard data</h3><p className="mb-3 mt-1 text-sm text-muted-foreground">Computed live from the governed metrics behind each widget.</p>
          <Select value={dash} onChange={(e) => setDash(e.target.value)} className="mb-3" aria-label="Dashboard"><option value="">Choose a dashboard…</option>{dashboards.data?.items.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select>
          <Buttons kind="dashboard" extra={`&dashboard_id=${dash}`} disabled={!dash} /></div></Card>
      </div>
    </div>
  );
}
