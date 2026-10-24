import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CloudUpload, FileSpreadsheet, Plus, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { DemoBadge, EmptyState, ErrorState, PageHeader, Pager, TableSkeleton, useDebounced } from "@/components/common";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Input, Select, Textarea } from "@/components/ui/form";
import { Progress } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, formatBytes, timeAgo } from "@/lib/utils";

const ACCEPT = ".csv,.tsv,.xlsx,.xls,.json,.jsonl,.ndjson,.parquet";

function UploadModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const toast = useToast();
  const nav = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const pick = (f?: File | null) => { if (!f) return; setFile(f); setErr(null); if (!name) setName(f.name.replace(/\.[^.]+$/, "")); };
  const reset = () => { setFile(null); setName(""); setDesc(""); setErr(null); };
  const submit = async () => {
    if (!file) return;
    setBusy(true); setErr(null);
    try {
      const fd = new FormData();
      fd.append("file", file); fd.append("name", name || file.name); if (desc) fd.append("description", desc);
      const r = await api.upload("/datasets/upload", fd);
      toast.success("Upload received", "Processing runs in the background. Track progress below.");
      qc.invalidateQueries({ queryKey: ["datasets"] });
      reset(); onClose();
      nav(`/app/datasets/${r.dataset.id}`);
    } catch (e) { setErr(e instanceof ApiError ? e.message : "Upload failed"); }
    finally { setBusy(false); }
  };
  return (
    <Modal open={open} onOpenChange={(o) => { if (!o) { reset(); onClose(); } }} title="Upload dataset" description="CSV, TSV, Excel, JSON/JSONL or Parquet. The file streams to the server and is processed by a background worker with DuckDB." className="max-w-xl"
      footer={<><Button variant="ghost" onClick={() => { reset(); onClose(); }}>Cancel</Button><Button onClick={submit} loading={busy} disabled={!file} data-testid="upload-submit"><CloudUpload className="h-4 w-4" />Upload & process</Button></>}>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); pick(e.dataTransfer.files?.[0]); }}
        className={cn("flex flex-col items-center rounded-2xl border-2 border-dashed p-8 text-center transition-colors", drag ? "border-accent bg-accent/5" : "bg-muted/40")}>
        {file ? (
          <div className="flex items-center gap-3"><FileSpreadsheet className="h-8 w-8 text-accent" /><div className="text-left"><p className="font-medium">{file.name}</p><p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p></div><button onClick={() => setFile(null)} aria-label="Remove file" className="rounded p-1 hover:bg-muted"><X className="h-4 w-4" /></button></div>
        ) : (<>
          <CloudUpload className="h-9 w-9 text-muted-foreground" aria-hidden />
          <p className="mt-2 text-sm font-medium">Drag a file here or</p>
          <Button variant="outline" size="sm" className="mt-2" onClick={() => input.current?.click()}>Choose file</Button>
        </>)}
        <input ref={input} type="file" accept={ACCEPT} className="sr-only" onChange={(e) => pick(e.target.files?.[0])} aria-label="Dataset file" data-testid="upload-input" />
      </div>
      <div className="mt-4 space-y-3">
        <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Dataset name" aria-label="Dataset name" data-testid="upload-name" />
        <Textarea value={desc} onChange={(e) => setDesc(e.target.value)} rows={2} placeholder="Description (optional)" aria-label="Description" />
        {err && <p role="alert" className="text-sm text-danger">{err}</p>}
      </div>
    </Modal>
  );
}

export default function Datasets() {
  const { can, user } = useAuth();
  const nav = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [sp, setSp] = useSearchParams();
  const [upload, setUpload] = useState(sp.get("upload") === "1");
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const [toDelete, setToDelete] = useState<any>(null);
  const list = useQuery({
    queryKey: ["datasets", dq, status, page],
    queryFn: () => api.get(`/datasets${qs({ q: dq, status, page, page_size: 12 })}`),
    refetchInterval: (query) => ((query.state.data as any)?.items?.some((d: any) => d.status === "pending" || d.status === "processing") ? 1500 : false),
    placeholderData: (p) => p,
  });
  const del = useMutation({
    mutationFn: (id: string) => api.del(`/datasets/${id}`),
    onSuccess: () => { toast.success("Dataset deleted"); setToDelete(null); qc.invalidateQueries({ queryKey: ["datasets"] }); },
    onError: (e: ApiError) => toast.error("Cannot delete", e.message),
  });
  const closeUpload = useCallback(() => { setUpload(false); if (sp.get("upload")) { sp.delete("upload"); setSp(sp, { replace: true }); } }, [sp, setSp]);
  useEffect(() => setPage(1), [dq, status]);

  return (
    <div>
      <PageHeader title="Datasets" description="Everything TARA and the Formula Lab can query. Files are converted to columnar Parquet and profiled in the background."
        actions={<>{user?.workspace.is_demo && <DemoBadge />}{can("dataset.write") && <><Link to="/app/connections"><Button variant="outline">Connections</Button></Link><Button onClick={() => setUpload(true)} data-testid="upload-open"><Plus className="h-4 w-4" />Upload dataset</Button></>}</>} />
      <Card className="mb-4 flex flex-wrap gap-2 p-3">
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search datasets…" className="min-w-[200px] flex-1" aria-label="Search datasets" />
        <Select value={status} onChange={(e) => setStatus(e.target.value)} className="w-44" aria-label="Status"><option value="">All statuses</option><option value="ready">Ready</option><option value="processing">Processing</option><option value="pending">Pending</option><option value="failed">Failed</option></Select>
      </Card>
      {list.isError ? <ErrorState error={list.error} retry={() => list.refetch()} /> : list.isLoading ? <Card><TableSkeleton /></Card> : list.data.items.length === 0 ? (
        <EmptyState title="No datasets yet" description="Upload a CSV, Excel, JSON or Parquet file, or connect a database, to start defining metrics." image={IMAGES.emptyStates.data} action={can("dataset.write") ? <Button onClick={() => setUpload(true)}>Upload dataset</Button> : undefined} />
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {list.data.items.map((d: any) => (
              <Card key={d.id} hover className="group relative flex flex-col p-5" data-testid="dataset-card">
                <Link to={`/app/datasets/${d.id}`} className="absolute inset-0 z-10 rounded-2xl" aria-label={`Open ${d.name}`} />
                <div className="flex items-start justify-between gap-2"><h3 className="min-w-0 truncate font-semibold">{d.name}</h3><StatusBadge status={d.status} /></div>
                <p className="mt-1 line-clamp-2 min-h-[2.5rem] text-sm text-muted-foreground">{d.description || d.original_filename || d.source_table || "—"}</p>
                {d.status === "ready" ? (
                  <dl className="mt-4 grid grid-cols-3 gap-2 text-sm"><div><dt className="text-xs text-muted-foreground">Rows</dt><dd className="font-medium tabular-nums">{d.row_count.toLocaleString()}</dd></div><div><dt className="text-xs text-muted-foreground">Columns</dt><dd className="font-medium">{d.column_count}</dd></div><div><dt className="text-xs text-muted-foreground">Complete</dt><dd className="font-medium">{d.completeness_pct ?? "—"}%</dd></div></dl>
                ) : d.status === "failed" ? <p className="mt-4 line-clamp-2 text-sm text-danger">{d.error}</p> : (
                  <div className="mt-4"><div className="mb-1.5 flex justify-between text-xs text-muted-foreground"><span>{d.stage || "queued"}</span><span>{d.progress}%</span></div><Progress value={d.progress} label={`${d.name} progress`} /></div>
                )}
                <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground"><Badge tone="outline">{d.source_type === "seed" ? "demo" : d.file_format}</Badge><span>{timeAgo(d.created_at)}</span>{d.size_bytes > 0 && <span>· {formatBytes(d.size_bytes)}</span>}
                  {can("dataset.delete") && <button className="relative z-20 ml-auto rounded-lg p-1.5 opacity-0 transition-opacity hover:bg-muted group-hover:opacity-100 focus-visible:opacity-100" aria-label={`Delete ${d.name}`} onClick={() => setToDelete(d)}><Trash2 className="h-4 w-4" /></button>}
                </div>
              </Card>
            ))}
          </div>
          <Pager page={page} pageSize={12} total={list.data.total} onPage={setPage} />
        </>
      )}
      <UploadModal open={upload} onClose={closeUpload} />
      <Modal open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)} title="Delete dataset?" description={`“${toDelete?.name}” and its processed files will be permanently removed. Metrics using it must be deprecated first.`}
        footer={<><Button variant="ghost" onClick={() => setToDelete(null)}>Cancel</Button><Button variant="danger" loading={del.isPending} onClick={() => del.mutate(toDelete.id)}>Delete</Button></>}><></></Modal>
    </div>
  );
}
