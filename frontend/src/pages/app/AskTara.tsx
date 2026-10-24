import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { AlertTriangle, BookOpenCheck, Filter, MessageSquarePlus, SendHorizonal, Sparkles, Trash2 } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { GroupedBars, SeriesChart } from "@/components/charts";
import { CodeBlock } from "@/components/common";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, streamAsk } from "@/lib/api";
import { cn, fmtDay, formatValue, ms } from "@/lib/utils";

interface Msg { id: string; role: "user" | "assistant"; text: string; payload?: any; pending?: boolean; stage?: string }

function Bold({ text }: { text: string }) {
  return <>{text.split(/(\*\*[^*]+\*\*)/g).map((p, i) => (p.startsWith("**") ? <strong key={i} className="font-semibold">{p.slice(2, -2)}</strong> : <span key={i}>{p}</span>))}</>;
}

function Answer({ m }: { m: Msg }) {
  const p = m.payload || {};
  const unit = p.sources?.[0] ? p.kpi?.unit ?? p.chart?.unit : undefined;
  const cols: string[] = p.table?.columns || [];
  return (
    <div className="space-y-3">
      <p className={cn("text-[15px] leading-relaxed", p.kind === "unsupported" && "text-muted-foreground")}>{p.kind === "unsupported" && <AlertTriangle className="-mt-0.5 mr-1.5 inline h-4 w-4 text-warning" />}<Bold text={m.text} />{m.pending && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-accent align-middle" />}</p>
      {p.notice && <p className="rounded-lg border border-warning/40 bg-warning/10 px-3 py-1.5 text-xs">{p.notice}</p>}
      {p.kpi && <div className="rounded-2xl border bg-card p-5"><p className="eyebrow">{p.kpi.label}</p><p className="display mt-1 text-5xl tabular-nums" data-testid="kpi-value">{p.kpi.formatted}</p></div>}
      {p.chart && <div className="rounded-2xl border bg-card p-4">{p.chart.type === "grouped" ? <GroupedBars data={p.chart.data} series={p.chart.series} unit={p.chart.unit} height={280} /> : <SeriesChart type={p.chart.type} data={p.chart.data} unit={p.chart.unit} height={240} name={p.sources?.[0]?.name || "Value"} />}</div>}
      {p.table && p.table.rows.length > 0 && !p.kpi && (
        <div className="max-h-72 overflow-auto rounded-2xl border bg-card"><table className="w-full text-sm"><thead className="sticky top-0 bg-card"><tr className="border-b text-left text-xs uppercase tracking-wider text-muted-foreground">{cols.map((c) => <th key={c} className="px-4 py-2.5 font-medium">{c === "value" ? p.sources?.[0]?.name || "value" : c === "share_pct" ? "share of region" : c.replace(/_/g, " ")}</th>)}</tr></thead>
          <tbody>{p.table.rows.map((r: any[], i: number) => <tr key={i} className="border-b last:border-0">{r.map((v, j) => <td key={j} className="px-4 py-2 tabular-nums">{cols[j] === "share_pct" ? `${v}%` : cols[j] === "value" ? formatValue(v, p.sources?.[0]?.unit ?? unit) : /^\d{4}-\d{2}-\d{2}$/.test(String(v)) ? fmtDay(String(v)) : String(v)}</td>)}</tr>)}</tbody></table></div>
      )}
      {p.kind === "answer" && (
        <div className="space-y-2 text-xs text-muted-foreground">
          <div className="flex flex-wrap items-center gap-1.5">
            <BookOpenCheck className="h-3.5 w-3.5" />Source:{p.sources.map((s: any) => <Link key={s.key} to={`/app/metrics/${s.metric_id}`}><Badge tone="accent">{s.name} · v{s.version}</Badge></Link>)}
            <span className="ml-1">on {p.sources[0].dataset}</span>
          </div>
          {(p.applied?.time_range || p.applied?.filters?.length > 0 || p.applied?.dimension) && (
            <div className="flex flex-wrap items-center gap-1.5"><Filter className="h-3.5 w-3.5" />Applied:
              {p.applied.time_range && <Badge tone="outline">{p.applied.time_range.label}</Badge>}
              {p.applied.compare_range && <Badge tone="outline">vs {p.applied.compare_range.label}</Badge>}
              {p.applied.dimension2 && <Badge tone="outline">split by {p.applied.dimension2}</Badge>}
              {p.applied.dimension && <Badge tone="outline">by {p.applied.grain ? `${p.applied.grain} of ${p.applied.dimension}` : p.applied.dimension}</Badge>}
              {p.applied.filters.map((f: any, i: number) => <Badge key={i} tone="outline">{f.column} {f.op} {String(f.value)}</Badge>)}
            </div>
          )}
          <details><summary className="cursor-pointer hover:text-foreground">Definition & query ({ms(p.query?.duration_ms)}, {p.query?.scanned_rows?.toLocaleString()} rows scanned · planner: {p.plan?.planner})</summary><CodeBlock className="mt-2">{p.sources[0].formula}{"\n\n"}{p.query?.sql}{"\n-- params: "}{JSON.stringify(p.query?.params)}</CodeBlock></details>
        </div>
      )}
    </div>
  );
}

export default function AskTara() {
  const qc = useQueryClient();
  const toast = useToast();
  const [sp, setSp] = useSearchParams();
  const [conv, setConv] = useState<string | null>(null);
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const end = useRef<HTMLDivElement>(null);
  const fired = useRef(false);
  const suggestions = useQuery({ queryKey: ["chat-suggestions"], queryFn: () => api.get("/chat/suggestions") });
  const convs = useQuery({ queryKey: ["conversations"], queryFn: () => api.get("/chat/conversations") });
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs]);

  const open = useCallback(async (id: string) => {
    const r = await api.get(`/chat/conversations/${id}`);
    setConv(id);
    setMsgs(r.messages.map((m: any) => ({ id: m.id, role: m.role, text: m.content, payload: m.payload })));
  }, []);

  const ask = useCallback(async (question: string) => {
    const text = question.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    const aid = `a${Date.now()}`;
    setMsgs((m) => [...m, { id: `u${Date.now()}`, role: "user", text }, { id: aid, role: "assistant", text: "", pending: true, stage: "planning" }]);
    try {
      let payload: any = {};
      let cid = conv;
      await streamAsk(text, conv, (ev, data) => {
        if (ev === "status") { cid = data.conversation_id; setConv(cid); }
        if (ev === "plan") payload = { ...payload, plan: data.plan, notice: data.notice };
        if (ev === "result") { payload = { ...payload, ...data }; setMsgs((m) => m.map((x) => (x.id === aid ? { ...x, payload } : x))); }
        if (ev === "text") setMsgs((m) => m.map((x) => (x.id === aid ? { ...x, text: x.text + data.delta } : x)));
        if (ev === "done") setMsgs((m) => m.map((x) => (x.id === aid ? { ...x, text: data.text, pending: false, payload } : x)));
      });
      qc.invalidateQueries({ queryKey: ["conversations"] });
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Something went wrong";
      setMsgs((m) => m.map((x) => (x.id === aid ? { ...x, pending: false, text: `I couldn't complete that request: ${msg}`, payload: { kind: "error" } } : x)));
      toast.error("Ask TARA failed", msg);
    } finally { setBusy(false); }
  }, [busy, conv, qc, toast]);

  useEffect(() => {
    const q = sp.get("q");
    if (q && !fired.current) { fired.current = true; sp.delete("q"); setSp(sp, { replace: true }); ask(q); }
  }, [sp, setSp, ask]);

  const newChat = () => { setConv(null); setMsgs([]); };
  const del = async (id: string) => { await api.del(`/chat/conversations/${id}`); if (conv === id) newChat(); qc.invalidateQueries({ queryKey: ["conversations"] }); };

  return (
    <div className="grid h-[calc(100vh-9.5rem)] min-h-[520px] gap-4 lg:grid-cols-[260px_1fr]">
      <Card className="hidden flex-col overflow-hidden lg:flex">
        <div className="border-b p-3"><Button variant="outline" className="w-full" onClick={newChat} data-testid="new-chat"><MessageSquarePlus className="h-4 w-4" />New conversation</Button></div>
        <div className="flex-1 space-y-0.5 overflow-y-auto p-2" aria-label="Conversation history">
          {convs.data?.items.map((c: any) => (
            <div key={c.id} className={cn("group flex items-center rounded-xl", conv === c.id && "bg-muted")}>
              <button onClick={() => open(c.id)} className="min-w-0 flex-1 truncate px-3 py-2 text-left text-sm hover:text-accent">{c.title}</button>
              <button onClick={() => del(c.id)} aria-label={`Delete ${c.title}`} className="mr-1 rounded p-1.5 opacity-0 hover:bg-card group-hover:opacity-100 focus-visible:opacity-100"><Trash2 className="h-3.5 w-3.5" /></button>
            </div>
          ))}
          {!convs.data?.items.length && <p className="p-3 text-xs text-muted-foreground">Your past questions appear here.</p>}
        </div>
      </Card>

      <Card className="flex flex-col overflow-hidden">
        <div className="flex items-center gap-2 border-b px-5 py-3"><Sparkles className="h-4 w-4 text-accent" /><h1 className="font-semibold">Ask TARA</h1><span className="ml-2 hidden text-xs text-muted-foreground sm:inline">Answers come from governed metrics only. If the data can't answer, TARA says so.</span></div>
        <div className="flex-1 space-y-6 overflow-y-auto p-5" aria-live="polite" data-testid="chat-log">
          {msgs.length === 0 && (
            <div className="mx-auto flex h-full max-w-xl flex-col items-center justify-center text-center">
              <span className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10"><Sparkles className="h-7 w-7 text-accent" /></span>
              <h2 className="display text-4xl">What would you like to know?</h2>
              <p className="mt-2 text-sm text-muted-foreground">Ask about any approved metric in plain English. Dates follow the Indian financial year (April to March) and amounts are in rupees.</p>
              <div className="mt-6 flex flex-wrap justify-center gap-2">{(suggestions.data?.items || []).map((s: string) => <button key={s} onClick={() => ask(s)} className="rounded-full border px-3.5 py-1.5 text-sm transition-colors hover:border-accent hover:bg-accent/5" data-testid="suggestion">{s}</button>)}</div>
              {suggestions.data && !suggestions.data.items.length && <p className="mt-4 text-sm text-warning">No approved metrics are available to query yet.</p>}
            </div>
          )}
          {msgs.map((m) => (
            <motion.div key={m.id} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className={cn("flex", m.role === "user" && "justify-end")}>
              {m.role === "user" ? <div className="max-w-[85%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-foreground">{m.text}</div> : (
                <div className="flex w-full max-w-3xl gap-3" data-testid="assistant-msg">
                  <span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-accent text-accent-foreground"><Sparkles className="h-3.5 w-3.5" /></span>
                  <div className="min-w-0 flex-1">{m.pending && !m.text && !m.payload ? <p className="flex items-center gap-2 text-sm text-muted-foreground"><Spinner />TARA is planning and querying…</p> : <Answer m={m} />}</div>
                </div>
              )}
            </motion.div>
          ))}
          <div ref={end} />
        </div>
        <form className="flex items-end gap-2 border-t p-3" onSubmit={(e) => { e.preventDefault(); ask(input); }}>
          <label htmlFor="ask-input" className="sr-only">Ask a question</label>
          <textarea id="ask-input" value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); ask(input); } }} rows={1} placeholder="Ask about revenue, orders, GST, refunds…" data-testid="ask-input"
            className="max-h-32 min-h-[44px] flex-1 resize-none rounded-xl border bg-card px-4 py-3 text-sm placeholder:text-muted-foreground/70 focus-visible:border-accent" />
          <Button type="submit" variant="accent" size="lg" disabled={!input.trim() || busy} aria-label="Send question" data-testid="ask-send"><SendHorizonal className="h-4 w-4" /></Button>
        </form>
      </Card>
    </div>
  );
}
