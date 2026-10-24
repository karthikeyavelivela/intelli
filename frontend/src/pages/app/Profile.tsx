import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { PageHeader } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Field, Input } from "@/components/ui/form";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { fmtDateTime } from "@/lib/utils";

export default function Profile() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user?.name || "");
  const [title, setTitle] = useState(user?.title || "");
  const [cur, setCur] = useState("");
  const [nw, setNw] = useState("");
  const matrix = useQuery({ queryKey: ["matrix"], queryFn: () => api.get("/permissions/matrix") });
  const save = useMutation({ mutationFn: () => api.patch("/auth/me", { name, title }), onSuccess: (r) => { setUser(r.user); toast.success("Profile updated"); }, onError: (e: ApiError) => toast.error("Could not save", e.message) });
  const pw = useMutation({ mutationFn: () => api.post("/auth/change-password", { current_password: cur, new_password: nw }), onSuccess: () => { toast.success("Password changed", "Other sessions were signed out."); setCur(""); setNw(""); }, onError: (e: ApiError) => toast.error("Could not change password", e.message) });
  if (!user) return null;
  const mine = matrix.data?.matrix.filter((m: any) => m[user.role]) || [];
  return (
    <div>
      <PageHeader title="Your profile" description="Personal details, password and what your role can do." />
      <div className="grid gap-4 lg:grid-cols-2">
        <Card><CardHeader title="Details" action={<Badge tone="solid">{user.role_label}</Badge>} /><CardBody className="space-y-4">
          <Field label="Full name">{(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
          <Field label="Job title">{(id) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
          <Field label="Email" hint="Email cannot be changed.">{(id) => <Input id={id} value={user.email} disabled />}</Field>
          <dl className="grid grid-cols-2 gap-2 text-sm"><dt className="text-muted-foreground">Workspace</dt><dd>{user.workspace.name}</dd><dt className="text-muted-foreground">Member since</dt><dd>{fmtDateTime(user.created_at)}</dd><dt className="text-muted-foreground">Last sign-in</dt><dd>{fmtDateTime(user.last_login)}</dd></dl>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={name.trim().length < 2}>Save profile</Button>
        </CardBody></Card>
        <Card><CardHeader title="Password" description={user.is_demo ? "Demo account passwords can't be changed." : undefined} /><CardBody className="space-y-4">
          <Field label="Current password">{(id) => <Input id={id} type="password" value={cur} onChange={(e) => setCur(e.target.value)} autoComplete="current-password" disabled={user.is_demo} />}</Field>
          <Field label="New password" hint="At least 8 characters with letters and digits.">{(id) => <Input id={id} type="password" value={nw} onChange={(e) => setNw(e.target.value)} autoComplete="new-password" disabled={user.is_demo} />}</Field>
          <Button variant="outline" onClick={() => pw.mutate()} loading={pw.isPending} disabled={user.is_demo || !cur || nw.length < 8}>Change password</Button>
        </CardBody></Card>
        <Card className="lg:col-span-2"><CardHeader title="What your role can do" description={`${mine.length} capabilities for ${user.role_label}`} /><CardBody><ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{mine.map((m: any) => <li key={m.capability} className="flex items-start gap-2 rounded-xl border p-2.5 text-sm"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />{m.label}</li>)}</ul></CardBody></Card>
      </div>
    </div>
  );
}
