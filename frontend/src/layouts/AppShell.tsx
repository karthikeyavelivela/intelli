import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity, BarChart3, Bell, BookOpenCheck, Cable, ChevronRight, Database, FileText, FlaskConical, GitCompare, History, LayoutDashboard,
  LayoutGrid, LogOut, Menu as MenuIcon, PanelLeftClose, PanelLeftOpen, Search, Settings as SettingsIcon, ShieldCheck, Sparkles, Users, Wand2, X, ScrollText, UserCircle,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { Logo, DemoBadge, useDebounced } from "@/components/common";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Menu, MenuContent, MenuItem, MenuLabel, MenuSeparator, MenuTrigger } from "@/components/ui/dropdown";
import { Modal } from "@/components/ui/dialog";
import { Input } from "@/components/ui/form";
import { Kbd } from "@/components/ui/misc";
import { api, qs } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { cn, timeAgo } from "@/lib/utils";

interface NavItem { to: string; label: string; icon: typeof Search; cap?: string; end?: boolean }
const NAV: { group: string; items: NavItem[] }[] = [
  { group: "Overview", items: [{ to: "/app/dashboard", label: "Dashboard", icon: LayoutDashboard }] },
  { group: "Semantic layer", items: [
    { to: "/app/metrics", label: "Metrics catalog", icon: BookOpenCheck },
    { to: "/app/conflicts", label: "Conflict center", icon: GitCompare, cap: "conflict.view" },
    { to: "/app/versions", label: "Version control", icon: History },
  ] },
  { group: "Data", items: [
    { to: "/app/datasets", label: "Datasets", icon: Database, end: true },
    { to: "/app/connections", label: "Connections", icon: Cable, cap: "dataset.write" },
  ] },
  { group: "TARA", items: [
    { to: "/app/ask", label: "Ask TARA", icon: Sparkles, cap: "chat.ask" },
    { to: "/app/generator", label: "Metric generator", icon: Wand2, cap: "ai.generate" },
  ] },
  { group: "Analysis", items: [
    { to: "/app/lab", label: "Formula Lab", icon: FlaskConical, cap: "formula.run" },
    { to: "/app/dashboards", label: "Dashboards", icon: LayoutGrid },
    { to: "/app/evaluation", label: "Evaluation", icon: BarChart3, cap: "evaluation.view" },
    { to: "/app/reports", label: "Reports & exports", icon: FileText, cap: "report.export" },
  ] },
  { group: "Workspace", items: [
    { to: "/app/notifications", label: "Activity", icon: Activity },
    { to: "/app/admin/users", label: "Users & workspace", icon: Users, cap: "user.manage" },
    { to: "/app/admin/audit", label: "Audit log", icon: ScrollText, cap: "audit.view" },
    { to: "/app/settings", label: "Settings", icon: SettingsIcon },
  ] },
];

const CRUMBS: Record<string, string> = {
  app: "Home", dashboard: "Dashboard", metrics: "Metrics catalog", conflicts: "Conflict center", versions: "Version control", datasets: "Datasets",
  connections: "Connections", ask: "Ask TARA", generator: "Metric generator", lab: "Formula Lab", dashboards: "Dashboards", evaluation: "Evaluation",
  reports: "Reports & exports", notifications: "Activity", admin: "Admin", users: "Users & workspace", audit: "Audit log", settings: "Settings", profile: "Profile", builder: "Builder", new: "New",
};

function Breadcrumbs() {
  const { pathname } = useLocation();
  const parts = pathname.split("/").filter(Boolean);
  if (parts.length < 2) return null;
  const crumbs = parts.map((p, i) => ({ label: CRUMBS[p] || "Details", to: "/" + parts.slice(0, i + 1).join("/"), last: i === parts.length - 1 }));
  return (
    <nav aria-label="Breadcrumb" className="mb-4 hidden items-center gap-1 text-xs text-muted-foreground sm:flex">
      {crumbs.slice(1).map((c, i) => (
        <span key={c.to} className="flex items-center gap-1">
          {i > 0 && <ChevronRight className="h-3 w-3" aria-hidden />}
          {c.last ? <span aria-current="page" className="font-medium text-foreground">{c.label}</span> : <Link to={c.to} className="hover:text-foreground">{c.label}</Link>}
        </span>
      ))}
    </nav>
  );
}

function SidebarNav({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const { can } = useAuth();
  return (
    <nav aria-label="Primary" className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
      {NAV.map((g) => {
        const items = g.items.filter((i) => !i.cap || can(i.cap));
        if (!items.length) return null;
        return (
          <div key={g.group}>
            {!collapsed && <div className="eyebrow mb-1.5 px-2.5">{g.group}</div>}
            <ul className="space-y-0.5">
              {items.map(({ to, label, icon: Icon, end }) => (
                <li key={to}>
                  <NavLink to={to} end={end} onClick={onNavigate} title={collapsed ? label : undefined}
                    className={({ isActive }) => cn("group relative flex items-center gap-3 rounded-xl px-2.5 py-2 text-sm font-medium transition-colors", collapsed && "justify-center", isActive ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/70 hover:text-foreground")}>
                    {({ isActive }) => (
                      <>
                        {isActive && <span className="absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-accent" aria-hidden />}
                        <Icon className={cn("h-[18px] w-[18px] shrink-0", isActive && "text-accent")} aria-hidden />
                        {!collapsed && <span className="truncate">{label}</span>}
                        {collapsed && <span className="sr-only">{label}</span>}
                      </>
                    )}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}

function GlobalSearch() {
  const nav = useNavigate();
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const dq = useDebounced(q, 250);
  const ref = useRef<HTMLInputElement>(null);
  const box = useRef<HTMLDivElement>(null);
  const { data } = useQuery({
    queryKey: ["search", dq],
    enabled: dq.length >= 2,
    queryFn: async () => {
      const [m, d] = await Promise.all([api.get(`/metrics${qs({ q: dq, page_size: 5 })}`), api.get(`/datasets${qs({ q: dq, page_size: 5 })}`)]);
      return { metrics: m.items, datasets: d.items };
    },
  });
  const pages = useMemo(() => NAV.flatMap((g) => g.items).filter((i) => (!i.cap || can(i.cap)) && q.length >= 1 && i.label.toLowerCase().includes(q.toLowerCase())), [q, can]);

  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); ref.current?.focus(); } };
    const c = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    window.addEventListener("keydown", k); document.addEventListener("mousedown", c);
    return () => { window.removeEventListener("keydown", k); document.removeEventListener("mousedown", c); };
  }, []);
  const go = (to: string) => { setOpen(false); setQ(""); nav(to); };
  const has = pages.length || data?.metrics?.length || data?.datasets?.length;
  return (
    <div ref={box} className="relative w-full max-w-md">
      <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" aria-hidden />
      <Input ref={ref} value={q} onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        placeholder="Search metrics, datasets, pages…" aria-label="Global search" className="h-9 rounded-full bg-muted pl-9 pr-14" data-testid="global-search" />
      <span className="absolute right-3 top-1/2 hidden -translate-y-1/2 sm:block"><Kbd>Ctrl K</Kbd></span>
      {open && q.length >= 1 && (
        <div className="absolute left-0 right-0 top-11 z-50 max-h-96 overflow-y-auto rounded-2xl border bg-card p-2 shadow-lift">
          {!has && <p className="p-3 text-sm text-muted-foreground">{dq.length < 2 ? "Keep typing…" : "No results"}</p>}
          {pages.length > 0 && <><div className="eyebrow px-2 py-1">Pages</div>{pages.map((p) => <button key={p.to} onClick={() => go(p.to)} className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm hover:bg-muted"><p.icon className="h-4 w-4 text-muted-foreground" />{p.label}</button>)}</>}
          {!!data?.metrics?.length && <><div className="eyebrow px-2 py-1">Metrics</div>{data.metrics.map((m: any) => <button key={m.id} onClick={() => go(`/app/metrics/${m.id}`)} className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm hover:bg-muted"><span className="truncate">{m.name}</span><span className="ml-2 text-xs capitalize text-muted-foreground">{m.department || m.status}</span></button>)}</>}
          {!!data?.datasets?.length && <><div className="eyebrow px-2 py-1">Datasets</div>{data.datasets.map((d: any) => <button key={d.id} onClick={() => go(`/app/datasets/${d.id}`)} className="flex w-full items-center justify-between rounded-lg px-2.5 py-2 text-left text-sm hover:bg-muted"><span className="truncate">{d.name}</span><span className="ml-2 text-xs text-muted-foreground">{d.row_count.toLocaleString()} rows</span></button>)}</>}
        </div>
      )}
    </div>
  );
}

function NotificationsBell() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const { data } = useQuery({ queryKey: ["notifications", "bell"], queryFn: () => api.get("/notifications?limit=8"), refetchInterval: 20000 });
  const unread = data?.unread ?? 0;
  const read = async (n: any) => { if (!n.read) { await api.post(`/notifications/${n.id}/read`); qc.invalidateQueries({ queryKey: ["notifications"] }); } if (n.link) nav(n.link); };
  return (
    <Menu>
      <MenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} className="relative" data-testid="bell">
          <Bell className="h-[18px] w-[18px]" />
          {unread > 0 && <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-accent-foreground">{unread > 9 ? "9+" : unread}</span>}
        </Button>
      </MenuTrigger>
      <MenuContent className="w-[22rem] p-0">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <span className="text-sm font-semibold">Notifications</span>
          <button className="text-xs text-accent hover:underline" onClick={async () => { await api.post("/notifications/read-all"); qc.invalidateQueries({ queryKey: ["notifications"] }); }}>Mark all read</button>
        </div>
        <div className="max-h-80 overflow-y-auto p-1.5">
          {!data?.items?.length && <p className="p-4 text-center text-sm text-muted-foreground">You're all caught up.</p>}
          {data?.items?.map((n: any) => (
            <MenuItem key={n.id} onSelect={() => read(n)} className="items-start gap-3">
              <span className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", n.read ? "bg-transparent" : "bg-accent")} />
              <span className="min-w-0 flex-1"><span className="block truncate text-sm font-medium">{n.title}</span>{n.body && <span className="line-clamp-2 text-xs text-muted-foreground">{n.body}</span>}<span className="text-[11px] text-muted-foreground">{timeAgo(n.created_at)}</span></span>
            </MenuItem>
          ))}
        </div>
        <MenuSeparator />
        <MenuItem onSelect={() => nav("/app/notifications")} className="justify-center text-accent">View all activity</MenuItem>
      </MenuContent>
    </Menu>
  );
}

function TaraQuickAsk() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const nav = useNavigate();
  const { can } = useAuth();
  if (!can("chat.ask")) return null;
  const go = (text: string) => { setOpen(false); setQ(""); nav(`/app/ask?q=${encodeURIComponent(text)}`); };
  return (
    <>
      <Button variant="accent" size="sm" onClick={() => setOpen(true)} aria-label="Ask TARA" data-testid="tara-quick"><Sparkles className="h-4 w-4" /><span className="hidden md:inline">Ask TARA</span></Button>
      <Modal open={open} onOpenChange={setOpen} title="Ask TARA" description="Ask a question about your governed metrics in plain English.">
        <form onSubmit={(e) => { e.preventDefault(); if (q.trim()) go(q.trim()); }} className="space-y-3">
          <Input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Which 5 states had the highest sales this year?" aria-label="Question for TARA" />
          <div className="flex flex-wrap gap-2">
            {["What was net revenue by month in the last quarter of this financial year?", "Which 5 states had the highest sales this year?", "Compare Diwali-season sales with the previous quarter"].map((s) => <button type="button" key={s} onClick={() => go(s)} className="rounded-full border px-3 py-1 text-xs hover:bg-muted">{s}</button>)}
          </div>
          <div className="flex justify-end"><Button type="submit" variant="accent" disabled={!q.trim()}>Ask</Button></div>
        </form>
      </Modal>
    </>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  if (!user) return null;
  const initials = user.name.split(" ").map((s) => s[0]).slice(0, 2).join("").toUpperCase();
  return (
    <Menu>
      <MenuTrigger asChild>
        <button className="flex items-center gap-2 rounded-full border p-1 pr-3 hover:bg-muted" aria-label="User menu" data-testid="user-menu">
          <span className="flex h-7 w-7 items-center justify-center rounded-full bg-primary text-xs font-semibold text-primary-foreground">{initials}</span>
          <span className="hidden text-sm font-medium lg:block">{user.name.split(" ")[0]}</span>
        </button>
      </MenuTrigger>
      <MenuContent>
        <MenuLabel><span className="block text-sm font-medium text-foreground">{user.name}</span>{user.email}<span className="mt-1 block text-[11px] uppercase tracking-wider">{user.role_label} · {user.workspace.name}</span></MenuLabel>
        <MenuSeparator />
        <MenuItem onSelect={() => nav("/app/profile")}><UserCircle className="h-4 w-4" />Profile</MenuItem>
        <MenuItem onSelect={() => nav("/app/settings")}><SettingsIcon className="h-4 w-4" />Settings</MenuItem>
        <MenuSeparator />
        <MenuItem onSelect={async () => { await logout(); nav("/login"); }} data-testid="logout"><LogOut className="h-4 w-4" />Sign out</MenuItem>
      </MenuContent>
    </Menu>
  );
}

export function AppShell() {
  const { user } = useAuth();
  const [collapsed, setCollapsed] = useState(() => { try { return localStorage.getItem("im-sidebar") === "1"; } catch { return false; } });
  const [drawer, setDrawer] = useState(false);
  const loc = useLocation();
  useEffect(() => setDrawer(false), [loc.pathname]);
  useEffect(() => { try { localStorage.setItem("im-sidebar", collapsed ? "1" : "0"); } catch { /* ignore */ } }, [collapsed]);
  const isBuilder = loc.pathname.includes("/dashboards/");

  return (
    <div className="flex min-h-screen bg-background">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70] focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground">Skip to content</a>
      <aside className={cn("sticky top-0 hidden h-screen shrink-0 flex-col border-r bg-card transition-[width] duration-200 lg:flex", collapsed ? "w-[68px]" : "w-64")}>
        <div className={cn("flex h-16 items-center border-b px-4", collapsed && "justify-center px-0")}>
          <Link to="/app/dashboard" aria-label="IntelliMetrics home">{collapsed ? <svg viewBox="0 0 32 32" className="h-7 w-7"><rect width="32" height="32" rx="8" className="fill-primary" /><path d="M8 22V10l8 8 8-8v12" fill="none" className="stroke-primary-foreground" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /></svg> : <Logo />}</Link>
        </div>
        <SidebarNav collapsed={collapsed} />
        <div className="border-t p-3">
          {!collapsed && <p className="mb-2 px-1 text-[11px] leading-snug text-muted-foreground" data-testid="university-note">University project &middot; synthetic demonstration data</p>}
          <Button variant="ghost" size="sm" className={cn("w-full", collapsed ? "px-0" : "justify-start")} onClick={() => setCollapsed((c) => !c)} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <><PanelLeftClose className="h-4 w-4" />Collapse</>}
          </Button>
        </div>
      </aside>

      <AnimatePresence>
        {drawer && (
          <>
            <motion.div className="fixed inset-0 z-40 bg-black/50 lg:hidden" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={() => setDrawer(false)} />
            <motion.aside className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col border-r bg-card lg:hidden" initial={{ x: -300 }} animate={{ x: 0 }} exit={{ x: -300 }} transition={{ type: "spring", damping: 28, stiffness: 300 }} aria-label="Mobile navigation">
              <div className="flex h-16 items-center justify-between border-b px-4"><Logo /><Button variant="ghost" size="icon" aria-label="Close menu" onClick={() => setDrawer(false)}><X className="h-5 w-5" /></Button></div>
              <SidebarNav collapsed={false} onNavigate={() => setDrawer(false)} />
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b bg-background/85 px-4 backdrop-blur-xl sm:px-6">
          <Button variant="ghost" size="icon" className="lg:hidden" aria-label="Open menu" onClick={() => setDrawer(true)}><MenuIcon className="h-5 w-5" /></Button>
          <GlobalSearch />
          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            {user?.workspace.is_demo && <span className="hidden xl:block"><DemoBadge /></span>}
            <TaraQuickAsk />
            <ThemeToggle compact />

            <NotificationsBell />
            <UserMenu />
          </div>
        </header>
        <main id="main" className={cn("flex-1 px-4 py-6 sm:px-6 lg:px-8", isBuilder ? "" : "mx-auto w-full max-w-[1360px]")}>
          <Breadcrumbs />
          <AnimatePresence mode="wait">
            <motion.div key={loc.pathname.split("/").slice(0, 4).join("/")} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.25, ease: "easeOut" }}>
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  );
}
