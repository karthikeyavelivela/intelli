import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Trash2, UserPlus } from "lucide-react";
import { useState } from "react";
import { DataTable, PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Field, Input, Select, Switch } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { timeAgo } from "@/lib/utils";

const ROLES = [["admin", "Admin"], ["data_analyst", "Data Analyst"], ["business_user", "Business User"], ["reviewer", "Reviewer"]];

export default function AdminUsers() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const toast = useToast();
  const [invite, setInvite] = useState(false);
  const [f, setF] = useState({ name: "", email: "", role: "business_user" });
  const [temp, setTemp] = useState<string | null>(null);
  const [wsName, setWsName] = useState("");
  const users = useQuery({ queryKey: ["users"], queryFn: () => api.get("/users") });
  const ws = useQuery({ queryKey: ["workspace"], queryFn: async () => { const w = await api.get("/workspaces/current"); setWsName(w.name); return w; } });
  const matrix = useQuery({ queryKey: ["matrix"], queryFn: () => api.get("/permissions/matrix") });
  const refresh = () => qc.invalidateQueries({ queryKey: ["users"] });
  const add = useMutation({ mutationFn: () => api.post("/users", f), onSuccess: (r) => { refresh(); setTemp(r.temporary_password); toast.success("User invited", r.user.email); setF({ name: "", email: "", role: "business_user" }); }, onError: (e: ApiError) => toast.error("Could not invite", e.message) });
  const patch = useMutation({ mutationFn: ({ id, body }: any) => api.patch(`/users/${id}`, body), onSuccess: () => { refresh(); toast.success("User updated"); }, onError: (e: ApiError) => toast.error("Could not update", e.message) });
  const remove = useMutation({ mutationFn: (id: string) => api.del(`/users/${id}`), onSuccess: () => { refresh(); toast.success("User removed"); }, onError: (e: ApiError) => toast.error("Could not remove", e.message) });
  const rename = useMutation({ mutationFn: () => api.patch("/workspaces/current", { name: wsName }), onSuccess: () => { toast.success("Workspace renamed"); qc.invalidateQueries({ queryKey: ["workspace"] }); }, onError: (e: ApiError) => toast.error("Failed", e.message) });
  const roles = ["admin", "data_analyst", "business_user", "reviewer"];

  return (
    <div className="space-y-6">
      <PageHeader title="Users & workspace" description="Invite teammates, assign roles and review exactly what each role may do." actions={<Button onClick={() => { setTemp(null); setInvite(true); }} data-testid="invite-user"><UserPlus className="h-4 w-4" />Invite user</Button>} />
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Members" />
          <DataTable rows={users.data?.items || []} rowKey={(u: any) => u.id} columns={[
            { key: "n", header: "Name", cell: (u: any) => <div><span className="font-medium">{u.name}</span>{u.is_demo && <Badge tone="accent" className="ml-2">DEMO</Badge>}<p className="text-xs text-muted-foreground">{u.email}</p></div> },
            { key: "r", header: "Role", cell: (u: any) => <Select value={u.role} disabled={u.id === me?.id} onChange={(e) => patch.mutate({ id: u.id, body: { role: e.target.value } })} className="h-9 w-44" aria-label={`Role for ${u.name}`}>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select> },
            { key: "a", header: "Active", cell: (u: any) => <Switch checked={u.is_active} onChange={(v) => u.id !== me?.id && patch.mutate({ id: u.id, body: { is_active: v } })} label={`Active: ${u.name}`} /> },
            { key: "l", header: "Last sign-in", cell: (u: any) => <span className="text-muted-foreground">{u.last_login ? timeAgo(u.last_login) : "never"}</span> },
            { key: "x", header: "", cell: (u: any) => u.id !== me?.id ? <Button size="sm" variant="ghost" aria-label={`Remove ${u.name}`} onClick={() => confirm(`Remove ${u.name}?`) && remove.mutate(u.id)}><Trash2 className="h-4 w-4" /></Button> : null },
          ]} />
        </Card>
        <Card><CardHeader title="Workspace" /><CardBody className="space-y-4">
          <Field label="Name">{(id) => <Input id={id} value={wsName} onChange={(e) => setWsName(e.target.value)} />}</Field>
          <Button variant="outline" onClick={() => rename.mutate()} loading={rename.isPending} disabled={wsName.trim().length < 2 || wsName === ws.data?.name}>Rename</Button>
          <dl className="grid grid-cols-2 gap-y-2 text-sm"><dt className="text-muted-foreground">Users</dt><dd>{ws.data?.stats.users}</dd><dt className="text-muted-foreground">Datasets</dt><dd>{ws.data?.stats.datasets}</dd><dt className="text-muted-foreground">Metrics</dt><dd>{ws.data?.stats.metrics}</dd><dt className="text-muted-foreground">Isolation</dt><dd>Strict: no cross-workspace reads</dd></dl>
        </CardBody></Card>
      </div>
      <Card>
        <CardHeader title="Permissions matrix" description="Enforced on every backend endpoint and mirrored in the UI" />
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground"><th className="px-4 py-3 font-medium">Capability</th>{roles.map((r) => <th key={r} className="px-4 py-3 text-center font-medium">{ROLES.find((x) => x[0] === r)![1]}</th>)}</tr></thead>
          <tbody>{matrix.data?.matrix.map((m: any) => <tr key={m.capability} className="border-b last:border-0"><td className="px-4 py-2.5">{m.label}<span className="ml-2 font-mono text-[11px] text-muted-foreground">{m.capability}</span></td>{roles.map((r) => <td key={r} className="px-4 py-2.5 text-center">{m[r] ? <Check className="mx-auto h-4 w-4 text-success" aria-label="allowed" /> : <span className="text-muted-foreground" aria-label="denied">—</span>}</td>)}</tr>)}</tbody></table></div>
      </Card>
      <Modal open={invite} onOpenChange={setInvite} title="Invite user" description="They join this workspace with the chosen role."
        footer={temp ? <Button onClick={() => setInvite(false)}>Done</Button> : <><Button variant="ghost" onClick={() => setInvite(false)}>Cancel</Button><Button loading={add.isPending} disabled={!f.name || !f.email} onClick={() => add.mutate()} data-testid="invite-confirm">Send invite</Button></>}>
        {temp ? (
          <div className="space-y-3" role="status"><p className="text-sm">User created. Share this temporary password securely; it is shown only once.</p><div className="flex items-center gap-2 rounded-xl border bg-muted p-3 font-mono text-sm"><span className="flex-1 break-all" data-testid="temp-password">{temp}</span><button aria-label="Copy" onClick={() => navigator.clipboard?.writeText(temp)} className="rounded p-1.5 hover:bg-card"><Copy className="h-4 w-4" /></button></div></div>
        ) : (
          <div className="space-y-3">
            <Field label="Full name">{(id) => <Input id={id} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} data-testid="invite-name" />}</Field>
            <Field label="Email">{(id) => <Input id={id} type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} data-testid="invite-email" />}</Field>
            <Field label="Role">{(id) => <Select id={id} value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{ROLES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>}</Field>
          </div>
        )}
      </Modal>
    </div>
  );
}
