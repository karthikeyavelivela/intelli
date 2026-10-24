import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Cable, CheckCircle2, Lock, Plus, Table2, Trash2, XCircle } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { EmptyState, ErrorState, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Field, Input, Select } from "@/components/ui/form";
import { Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/utils";

const BLANK = { name: "", kind: "postgres", host: "", port: 5432, database: "", username: "", password: "" };

function Tables({ conn, onClose }: { conn: any; onClose: () => void }) {
  const nav = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["conn-tables", conn.id], queryFn: () => api.get(`/connections/${conn.id}/tables`), retry: false });
  const imp = useMutation({
    mutationFn: (t: any) => api.post(`/connections/${conn.id}/import`, { table: t.schema && conn.kind === "postgres" && t.schema !== "public" ? `${t.schema}.${t.table}` : t.table }),
    onSuccess: (r) => { toast.success("Import started", "Streaming in chunks, read-only."); qc.invalidateQueries({ queryKey: ["datasets"] }); onClose(); nav(`/app/datasets/${r.dataset.id}`); },
    onError: (e: ApiError) => toast.error("Import failed", e.message),
  });
  return (
    <Modal open onOpenChange={(o) => !o && onClose()} title={`Tables in ${conn.database}`} description="Importing streams the table in chunks into Parquet using a read-only session.">
      {q.isLoading ? <p className="flex items-center gap-2 text-sm"><Spinner />Loading…</p> : q.isError ? <p role="alert" className="text-sm text-danger">{(q.error as ApiError).message}</p> : (
        <ul className="max-h-80 space-y-1 overflow-y-auto">
          {q.data.items.map((t: any) => <li key={`${t.schema}.${t.table}`} className="flex items-center justify-between rounded-xl border p-2.5 text-sm"><span className="flex items-center gap-2"><Table2 className="h-4 w-4 text-muted-foreground" />{t.schema}.{t.table}</span><Button size="sm" variant="outline" loading={imp.isPending && imp.variables?.table === t.table} onClick={() => imp.mutate(t)}>Import</Button></li>)}
          {!q.data.items.length && <p className="text-sm text-muted-foreground">No tables found.</p>}
        </ul>
      )}
    </Modal>
  );
}

export default function Connections() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<any>(BLANK);
  const [browse, setBrowse] = useState<any>(null);
  const list = useQuery({ queryKey: ["connections"], queryFn: () => api.get("/connections") });
  const create = useMutation({
    mutationFn: () => api.post("/connections", { ...f, port: Number(f.port) }),
    onSuccess: () => { toast.success("Connection saved", "Credentials are encrypted at rest."); setOpen(false); setF(BLANK); qc.invalidateQueries({ queryKey: ["connections"] }); },
    onError: (e: ApiError) => toast.error("Could not save", e.message),
  });
  const test = useMutation({
    mutationFn: (id: string) => api.post(`/connections/${id}/test`),
    onSuccess: (r) => { r.ok ? toast.success("Connected", r.message) : toast.error("Connection failed", r.message); qc.invalidateQueries({ queryKey: ["connections"] }); },
  });
  const del = useMutation({ mutationFn: (id: string) => api.del(`/connections/${id}`), onSuccess: () => { qc.invalidateQueries({ queryKey: ["connections"] }); toast.success("Connection removed"); }, onError: (e: ApiError) => toast.error("Failed", e.message) });
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value, ...(k === "kind" ? { port: e.target.value === "mysql" ? 3306 : 5432 } : {}) });

  return (
    <div>
      <PageHeader title="Connections" description="Connect PostgreSQL or MySQL. Credentials are encrypted at rest and the session is always read-only."
        actions={<Button onClick={() => setOpen(true)} data-testid="new-connection"><Plus className="h-4 w-4" />New connection</Button>} />
      <div className="mb-4 flex items-center gap-2 rounded-xl border bg-muted/50 p-3 text-sm text-muted-foreground"><Lock className="h-4 w-4 shrink-0 text-accent" />Passwords are encrypted with Fernet before storage and are never returned by the API or written to logs.</div>
      {list.isError ? <ErrorState error={list.error} /> : list.data?.items.length === 0 ? <EmptyState title="No connections yet" description="Add a database to import tables as datasets." image={IMAGES.emptyStates.quiet} icon={<Cable className="h-6 w-6" />} /> : (
        <div className="grid gap-4 md:grid-cols-2">
          {list.data?.items.map((c: any) => (
            <Card key={c.id} className="p-5">
              <div className="flex items-start justify-between gap-2"><div><h3 className="font-semibold">{c.name}</h3><p className="font-mono text-xs text-muted-foreground">{c.username}@{c.host}:{c.port}/{c.database}</p></div><Badge tone="outline">{c.kind}</Badge></div>
              <div className="mt-3 flex items-center gap-2 text-sm">
                {c.last_status === "ok" ? <><CheckCircle2 className="h-4 w-4 text-success" />Connected {timeAgo(c.last_tested_at)}</> : c.last_status === "failed" ? <><XCircle className="h-4 w-4 text-danger" /><span className="truncate text-danger" title={c.last_error}>{c.last_error}</span></> : <span className="text-muted-foreground">Not tested yet</span>}
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="outline" loading={test.isPending && test.variables === c.id} onClick={() => test.mutate(c.id)}>Test</Button>
                <Button size="sm" variant="outline" onClick={() => setBrowse(c)}>Browse tables</Button>
                {can("dataset.delete") && <Button size="sm" variant="ghost" className="ml-auto" aria-label={`Delete ${c.name}`} onClick={() => del.mutate(c.id)}><Trash2 className="h-4 w-4" /></Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={open} onOpenChange={setOpen} title="New connection" description="Use a read-only database role whenever possible." className="max-w-xl"
        footer={<><Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button><Button onClick={() => create.mutate()} loading={create.isPending} disabled={!f.name || !f.host || !f.database || !f.username}>Save connection</Button></>}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name" className="sm:col-span-2">{(id) => <Input id={id} value={f.name} onChange={set("name")} placeholder="Production replica" />}</Field>
          <Field label="Type">{(id) => <Select id={id} value={f.kind} onChange={set("kind")}><option value="postgres">PostgreSQL</option><option value="mysql">MySQL</option></Select>}</Field>
          <Field label="Port">{(id) => <Input id={id} type="number" value={f.port} onChange={set("port")} />}</Field>
          <Field label="Host" className="sm:col-span-2">{(id) => <Input id={id} value={f.host} onChange={set("host")} placeholder="db.internal.example.com" />}</Field>
          <Field label="Database">{(id) => <Input id={id} value={f.database} onChange={set("database")} />}</Field>
          <Field label="Username">{(id) => <Input id={id} value={f.username} onChange={set("username")} autoComplete="off" />}</Field>
          <Field label="Password" className="sm:col-span-2">{(id) => <Input id={id} type="password" value={f.password} onChange={set("password")} autoComplete="new-password" />}</Field>
        </div>
      </Modal>
      {browse && <Tables conn={browse} onClose={() => setBrowse(null)} />}
    </div>
  );
}
