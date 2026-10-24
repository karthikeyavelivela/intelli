import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { DataTable, ErrorState, PageHeader, Pager, TableSkeleton, useDebounced } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input, Select } from "@/components/ui/form";
import { api, qs } from "@/lib/api";
import { fmtDateTime } from "@/lib/utils";

export default function AuditLog() {
  const [q, setQ] = useState("");
  const dq = useDebounced(q);
  const [entity, setEntity] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => setPage(1), [dq, entity]);
  const list = useQuery({ queryKey: ["audit", dq, entity, page], queryFn: () => api.get(`/admin/audit-logs${qs({ q: dq, entity_type: entity, page, page_size: 25 })}`), placeholderData: (p) => p });
  return (
    <div>
      <PageHeader title="Audit log" description="Every sensitive action: who did what, to which entity, from where, with the request id for tracing." />
      <Card className="mb-4 flex flex-wrap gap-2 p-3"><Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter by action or user…" className="min-w-[200px] flex-1" aria-label="Filter audit log" />
        <Select value={entity} onChange={(e) => setEntity(e.target.value)} className="w-44" aria-label="Entity type"><option value="">All entities</option>{["metric", "dataset", "conflict", "user", "dashboard", "connection", "workspace", "report", "conversation"].map((e) => <option key={e}>{e}</option>)}</Select></Card>
      {list.isError ? <ErrorState error={list.error} /> : list.isLoading ? <Card><TableSkeleton /></Card> : (
        <Card><DataTable dense rows={list.data.items} rowKey={(a: any) => a.id} columns={[
          { key: "t", header: "Time", cell: (a: any) => <span className="whitespace-nowrap text-muted-foreground">{fmtDateTime(a.created_at)}</span> },
          { key: "u", header: "User", cell: (a: any) => a.user_email || "system" },
          { key: "a", header: "Action", cell: (a: any) => <code className="text-xs">{a.action}</code> },
          { key: "e", header: "Entity", cell: (a: any) => a.entity_type ? <Badge tone="outline">{a.entity_type}</Badge> : "—" },
          { key: "d", header: "Details", cell: (a: any) => <span className="line-clamp-2 max-w-md break-words font-mono text-[11px] text-muted-foreground">{JSON.stringify(a.details)}</span> },
          { key: "r", header: "Request", cell: (a: any) => <span className="font-mono text-[11px] text-muted-foreground">{a.request_id}</span> },
        ]} /><Pager page={page} pageSize={25} total={list.data.total} onPage={setPage} /></Card>
      )}
    </div>
  );
}
