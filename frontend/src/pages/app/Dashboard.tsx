import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Activity, ArrowUpRight, BookOpenCheck, Database, GitCompare, Gauge, ShieldCheck, Sparkles, Upload, Wand2, Zap } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { SeriesChart } from "@/components/charts";
import { AnimatedNumber, DemoBadge, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { Badge, StatusBadge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Progress, Skeleton } from "@/components/ui/misc";
import { IMAGES } from "@/config/images";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, timeAgo } from "@/lib/utils";

function Kpi({ icon: Icon, label, value, unit, sub, to, decimals, suffix, tone }: { icon: any; label: string; value: number | null | undefined; unit?: string; sub?: string; to?: string; decimals?: number; suffix?: string; tone?: "danger" }) {
  const body = (
    <Card hover className="h-full p-5">
      <div className="flex items-center justify-between"><span className="text-sm text-muted-foreground">{label}</span><Icon className={cn("h-4 w-4", tone === "danger" ? "text-danger" : "text-accent")} aria-hidden /></div>
      <div className="mt-3 text-3xl font-semibold tracking-tight tabular-nums"><AnimatedNumber value={value} unit={unit} decimals={decimals} />{value !== null && value !== undefined ? suffix : null}</div>
      {sub && <p className="mt-1 text-xs text-muted-foreground">{sub}</p>}
    </Card>
  );
  return to ? <Link to={to} className="block rounded-2xl" aria-label={label}>{body}</Link> : body;
}

export default function Dashboard() {
  const { user, can } = useAuth();
  const nav = useNavigate();
  const q = useQuery({ queryKey: ["overview"], queryFn: () => api.get("/overview"), refetchInterval: 15000 });
  const act = useQuery({ queryKey: ["activity"], queryFn: () => api.get("/activity?limit=8") });
  const d = q.data;
  const hour = new Date().getHours();
  const greet = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  if (q.isError) return <ErrorState error={q.error} retry={() => q.refetch()} />;

  const actions = [
    can("dataset.write") && { icon: Upload, label: "Upload data", to: "/app/datasets?upload=1", testid: "qa-upload" },
    can("metric.write") && { icon: BookOpenCheck, label: "Create metric", to: "/app/metrics?new=1", testid: "qa-metric" },
    can("conflict.view") && { icon: GitCompare, label: "Check conflicts", to: "/app/conflicts", testid: "qa-conflicts" },
    can("chat.ask") && { icon: Sparkles, label: "Ask TARA", to: "/app/ask", testid: "qa-ask" },
  ].filter(Boolean) as { icon: any; label: string; to: string; testid: string }[];

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={user?.workspace.name}
        title={<>{greet}, {user?.name.split(" ")[0]}</>}
        description="Your governed metrics, data health and conflicts at a glance. Every number below is computed live from your workspace."
        actions={user?.workspace.is_demo ? <DemoBadge /> : undefined}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 xl:grid-cols-6">
        {q.isLoading ? Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-[116px] rounded-2xl" />) : (
          <>
            <Kpi icon={BookOpenCheck} label="Total metrics" value={d.kpis.total_metrics} sub={`${d.kpis.published_metrics} published · ${d.kpis.in_review} in review`} to="/app/metrics" />
            <Kpi icon={Database} label="Connected datasets" value={d.kpis.connected_datasets} sub={d.kpis.processing_datasets ? `${d.kpis.processing_datasets} processing` : "all ready"} to="/app/datasets" />
            <Kpi icon={GitCompare} label="Active conflicts" value={d.kpis.active_conflicts} sub={`${d.kpis.resolved_conflicts} resolved`} to="/app/conflicts" tone={d.kpis.active_conflicts ? "danger" : undefined} />
            <Kpi icon={ShieldCheck} label="Validation pass rate" value={d.kpis.validation_pass_rate === null ? null : d.kpis.validation_pass_rate * 100} decimals={0} suffix="%" sub={`${d.kpis.validation_checks} metric definitions`} to="/app/evaluation" />
            <Kpi icon={Zap} label="Query success" value={d.kpis.query_success_rate === null ? null : d.kpis.query_success_rate * 100} decimals={1} suffix="%" sub="all executions" />
            <Kpi icon={Gauge} label="Avg query time" value={d.kpis.avg_query_ms} decimals={0} suffix=" ms" sub="DuckDB, read-only" />
          </>
        )}
      </div>

      {d && d.kpis.active_conflicts === 0 && d.kpis.resolved_conflicts === 0 && can("conflict.detect") && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex flex-col items-start justify-between gap-3 rounded-2xl border border-accent/30 bg-accent/5 p-4 sm:flex-row sm:items-center">
          <p className="text-sm"><span className="font-semibold">TARA hasn't compared your definitions yet.</span> Run conflict detection to see whether departments disagree on any metric.</p>
          <Button size="sm" variant="accent" onClick={() => nav("/app/conflicts?detect=1")}>Run detection</Button>
        </motion.div>
      )}

      {!!actions.length && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Quick actions">
          {actions.map((a) => (
            <Link key={a.label} to={a.to} data-testid={a.testid} className="group card card-hover flex items-center gap-3 p-4">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-muted transition-colors group-hover:bg-accent group-hover:text-accent-foreground"><a.icon className="h-5 w-5" /></span>
              <span className="font-medium">{a.label}</span><ArrowUpRight className="ml-auto h-4 w-4 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
            </Link>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Revenue by month" description={d?.charts.revenue_by_month ? `${d.charts.revenue_by_month.metric} · governed v${d.charts.revenue_by_month.version}` : "From the published Revenue metric"} />
          <CardBody>
            {q.isLoading ? <Skeleton className="h-[260px]" /> : d.charts.revenue_by_month ? <SeriesChart type="area" data={d.charts.revenue_by_month.data} unit={d.charts.revenue_by_month.unit} name="Revenue" /> : <EmptyState title="No published Revenue metric yet" description="Publish a metric named Revenue to see it here." image={IMAGES.emptyStates.data} />}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Revenue by region" description="Top regions, all time" />
          <CardBody>
            {q.isLoading ? <Skeleton className="h-[260px]" /> : d.charts.revenue_by_region ? <SeriesChart type="bar" data={d.charts.revenue_by_region.data} unit={d.charts.revenue_by_region.unit} name="Revenue" /> : <p className="py-16 text-center text-sm text-muted-foreground">No data</p>}
          </CardBody>
        </Card>
        <Card className="lg:col-span-2">
          <CardHeader title="Orders by month" description="Performance trend" />
          <CardBody>{q.isLoading ? <Skeleton className="h-[220px]" /> : d.charts.orders_by_month ? <SeriesChart type="line" data={d.charts.orders_by_month.data} unit={d.charts.orders_by_month.unit} name="Orders" height={220} /> : <p className="py-14 text-center text-sm text-muted-foreground">No published Orders metric</p>}</CardBody>
        </Card>
        <Card>
          <CardHeader title="Recent uploads" action={<Link className="text-xs text-accent hover:underline" to="/app/datasets">All</Link>} />
          <CardBody className="space-y-3">
            {q.isLoading ? <Skeleton className="h-24" /> : d.recent_uploads.length === 0 ? <p className="text-sm text-muted-foreground">No datasets yet.</p> : d.recent_uploads.map((u: any) => (
              <Link to={`/app/datasets/${u.id}`} key={u.id} className="block rounded-xl p-2 hover:bg-muted">
                <div className="flex items-center justify-between gap-2"><span className="truncate text-sm font-medium">{u.name}</span><StatusBadge status={u.status} /></div>
                {u.status === "ready" ? <p className="text-xs text-muted-foreground">{u.row_count.toLocaleString()} rows · {timeAgo(u.created_at)}</p> : <Progress value={u.progress} className="mt-2" />}
              </Link>
            ))}
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader title="Recent metric changes" action={<Link className="text-xs text-accent hover:underline" to="/app/versions">History</Link>} />
          <CardBody className="space-y-1">
            {q.isLoading ? <Skeleton className="h-32" /> : d.recent_changes.map((c: any, i: number) => (
              <Link key={i} to={`/app/versions/${c.metric_id}`} className="flex items-start gap-3 rounded-xl p-2 hover:bg-muted">
                <Badge tone="outline" className="mt-0.5 font-mono">v{c.version}</Badge>
                <span className="min-w-0 text-sm"><span className="block truncate font-medium">{c.metric_name}</span><span className="block truncate text-xs text-muted-foreground">{c.summary} · {c.author || "system"} · {timeAgo(c.created_at)}</span></span>
              </Link>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Notifications" action={<Link className="text-xs text-accent hover:underline" to="/app/notifications">All</Link>} />
          <CardBody className="space-y-1">
            {q.isLoading ? <Skeleton className="h-32" /> : d.notifications.length === 0 ? <p className="text-sm text-muted-foreground">Nothing new.</p> : d.notifications.map((n: any) => (
              <Link key={n.id} to={n.link || "/app/notifications"} className="block rounded-xl p-2 hover:bg-muted">
                <span className="block truncate text-sm font-medium">{n.title}</span>
                {n.body && <span className="line-clamp-2 text-xs text-muted-foreground">{n.body}</span>}
              </Link>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Activity feed" action={<Activity className="h-4 w-4 text-muted-foreground" />} />
          <CardBody className="space-y-2.5">
            {act.isLoading ? <Skeleton className="h-32" /> : act.data?.items.slice(0, 8).map((a: any) => (
              <div key={a.id} className="flex items-start gap-2.5 text-sm">
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" aria-hidden />
                <span className="min-w-0"><span className="font-medium">{a.action.replace(/\./g, " › ").replace(/_/g, " ")}</span>{a.details?.name || a.details?.key ? <span className="text-muted-foreground"> · {a.details.name || a.details.key}</span> : null}<span className="block text-xs text-muted-foreground">{a.user_email?.split("@")[0] || "system"} · {timeAgo(a.created_at)}</span></span>
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
