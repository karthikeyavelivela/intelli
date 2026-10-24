import { motion } from "framer-motion";
import { ArrowRight, Check, ChevronDown, GitCompare, GraduationCap, History, ShieldCheck, Sparkles, Database, FlaskConical, LayoutGrid, BookOpenCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { SafeImage } from "@/components/SafeImage";
import { Button } from "@/components/ui/button";
import { IMAGES } from "@/config/images";
import { cn } from "@/lib/utils";

const fade = { initial: { opacity: 0, y: 24 }, whileInView: { opacity: 1, y: 0 }, viewport: { once: true, margin: "-80px" }, transition: { duration: 0.55, ease: "easeOut" as const } };

const FEATURES = [
  { icon: BookOpenCheck, title: "A governed semantic layer", text: "Exactly one published definition per metric, with owners, approvals, dependencies and units.", img: IMAGES.features.metrics },
  { icon: Database, title: "Datasets at real scale", text: "CSV, Excel, JSON, Parquet, PostgreSQL and MySQL are processed in background workers with DuckDB.", img: IMAGES.features.datasets },
  { icon: GitCompare, title: "Conflict detection", text: "Deterministic checks catch the Finance-vs-Sales revenue problem before a board meeting does.", img: IMAGES.features.conflicts },
  { icon: FlaskConical, title: "Safe Formula Lab", text: "A real parser and AST compile to parameterized SQL. Raw SQL never reaches the database.", img: IMAGES.features.formula },
  { icon: History, title: "Immutable version history", text: "Every change is a new version. Roll back by creating another one. Audit everything.", img: IMAGES.features.versions },
  { icon: LayoutGrid, title: "Dashboards that don't drift", text: "Widgets read the live governed definition, or a version you pin on purpose.", img: IMAGES.features.dashboards },
];

const FAQ = [
  ["Does TARA make up numbers?", "No. TARA only produces a structured query plan. The numbers always come from executing governed metrics against your data through the safe compiler. If the data can't answer, TARA says so."],
  ["Do I need an AI key?", "No. Without a key TARA runs in a clearly labelled offline deterministic mode. Add an OpenAI or Gemini key (backend only) for richer metric generation and question planning."],
  ["How big can my datasets be?", "Uploads stream to disk and are converted to Parquet by DuckDB in background workers, never inside an HTTP request or the browser. The demo ships a 62,000-row synthetic Indian retail sales table (INR, GST, April-March financial year)."],
  ["Is user SQL ever executed?", "Never. Formulas use a restricted grammar that is parsed to an AST and compiled to parameterized SQL, with column validation, query timeouts and row limits."],
  ["How is my data isolated?", "Every row belongs to a workspace and every endpoint enforces workspace isolation and role-based access. Connection credentials are encrypted at rest and used read-only."],
];

export default function Landing() {
  const { hash } = useLocation();
  const [open, setOpen] = useState<number | null>(0);
  useEffect(() => {
    if (hash) setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: "smooth" }), 80);
  }, [hash]);

  return (
    <>
      {/* HERO */}
      <section className="relative overflow-hidden border-b">
        <div className="grid-bg absolute inset-0 -z-10 opacity-50" aria-hidden />
        <div className="container grid items-center gap-12 py-16 lg:grid-cols-[1.1fr_1fr] lg:py-24">
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
            <span className="inline-flex items-center gap-2 rounded-full border bg-card px-3 py-1 text-xs font-medium"><Sparkles className="h-3.5 w-3.5 text-accent" /> Meet TARA, your governed AI analyst</span>
            <span className="ml-2 inline-flex items-center gap-1.5 rounded-full border border-dashed px-3 py-1 text-xs font-medium text-muted-foreground" data-testid="university-badge"><GraduationCap className="h-3.5 w-3.5" /> University project</span>
            <h1 className="display mt-6 text-5xl leading-[1.02] sm:text-7xl">One number.<br /><em className="text-accent">Every</em> team.</h1>
            <p className="mt-6 max-w-xl text-lg text-muted-foreground">IntelliMetrics AI is a semantic layer where each business metric has one governed definition, conflicts are caught automatically, and anyone can ask questions in plain English with answers they can trust.</p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link to="/register"><Button size="lg">Get started <ArrowRight className="h-4 w-4" /></Button></Link>
              <Link to="/login"><Button size="lg" variant="outline" data-testid="hero-demo">Explore the demo</Button></Link>
              <Link to="/about"><Button size="lg" variant="ghost">About this project</Button></Link>
            </div>
            <dl className="mt-10 grid max-w-md grid-cols-3 gap-6">
              {[["62k+", "demo sales rows"], ["1", "definition per metric"], ["0", "invented numbers"]].map(([n, l]) => <div key={l}><dt className="display text-3xl">{n}</dt><dd className="text-xs text-muted-foreground">{l}</dd></div>)}
            </dl>
          </motion.div>
          <motion.div initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.1 }} className="relative">
            <SafeImage image={IMAGES.hero.main} eager className="aspect-[4/3] rounded-3xl border shadow-lift" />
            <div className="card absolute -bottom-6 -left-4 w-64 p-4 sm:-left-8">
              <p className="eyebrow">Revenue · Q2 FY 2026-27</p>
              <p className="display mt-1 text-3xl">₹2.4 Cr</p>
              <p className="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground"><ShieldCheck className="h-3.5 w-3.5 text-accent" />Governed definition v2 · illustrative figure</p>
            </div>
          </motion.div>
        </div>
      </section>

      {/* FEATURES */}
      <section className="container py-20" id="features">
        <motion.div {...fade} className="mx-auto max-w-2xl text-center">
          <p className="eyebrow">Platform</p>
          <h2 className="display mt-3 text-4xl sm:text-5xl">Everything between raw data and a trusted answer</h2>
        </motion.div>
        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <motion.article key={f.title} {...fade} transition={{ ...fade.transition, delay: (i % 3) * 0.08 }} className="card card-hover overflow-hidden">
              <SafeImage image={f.img} className="h-44" />
              <div className="p-5">
                <f.icon className="mb-3 h-5 w-5 text-accent" aria-hidden />
                <h3 className="font-semibold">{f.title}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{f.text}</p>
              </div>
            </motion.article>
          ))}
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section className="border-y bg-muted/40 py-20" id="how">
        <div className="container">
          <motion.div {...fade} className="mx-auto max-w-2xl text-center"><p className="eyebrow">How it works</p><h2 className="display mt-3 text-4xl sm:text-5xl">From upload to governed answer in four steps</h2></motion.div>
          <ol className="mt-14 grid gap-5 md:grid-cols-4">
            {[
              ["Connect", "Upload files or connect PostgreSQL / MySQL. Profiling runs in the background."],
              ["Define", "Describe a metric to TARA or write a formula. It is validated against your real schema."],
              ["Govern", "Detect conflicts, review, approve and publish. One definition wins; every change is a version."],
              ["Ask", "Anyone asks in plain English and gets a table, chart and the exact definition used."],
            ].map(([t, d], i) => (
              <motion.li key={t} {...fade} transition={{ ...fade.transition, delay: i * 0.08 }} className="card p-6">
                <span className="display text-5xl text-accent">{i + 1}</span>
                <h3 className="mt-2 font-semibold">{t}</h3>
                <p className="mt-1.5 text-sm text-muted-foreground">{d}</p>
              </motion.li>
            ))}
          </ol>
        </div>
      </section>

      {/* TARA SHOWCASE */}
      <section className="container grid items-center gap-12 py-20 lg:grid-cols-2" id="tara">
        <motion.div {...fade}>
          <p className="eyebrow">TARA</p>
          <h2 className="display mt-3 text-4xl sm:text-5xl">An AI analyst with a conscience</h2>
          <p className="mt-4 text-muted-foreground">TARA turns questions into a validated query plan. It checks your permissions, compiles safe SQL through the same engine as the Formula Lab, and shows the metric version, filters and formula behind every number.</p>
          <ul className="mt-6 space-y-3 text-sm">
            {["Grounded in your real dataset schema and existing metrics", "Structured JSON validated before anything runs", "Says \"I can't answer that\" instead of guessing", "Works offline in a clearly labelled deterministic mode"].map((t) => <li key={t} className="flex gap-2"><Check className="mt-0.5 h-4 w-4 shrink-0 text-accent" />{t}</li>)}
          </ul>
        </motion.div>
        <motion.div {...fade} className="card overflow-hidden" aria-label="Example conversation with TARA">
          <div className="flex items-center gap-2 border-b px-5 py-3"><Sparkles className="h-4 w-4 text-accent" /><span className="text-sm font-semibold">Ask TARA</span><span className="ml-auto rounded-full border px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted-foreground">Example</span></div>
          <div className="space-y-4 p-5 text-sm">
            <div className="ml-auto max-w-[80%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-primary-foreground">What was net revenue by month in the last quarter of this financial year?</div>
            <div className="max-w-[92%] rounded-2xl rounded-bl-md border bg-muted/50 p-4">
              <p>Revenue by month for Q2 FY 2026-27 (01-Jul-2026 to 30-Sep-2026): 3 periods, in rupees, using the governed definition.</p>
              <div className="mt-3 flex h-24 items-end gap-3" aria-hidden>{[62, 78, 70].map((h, i) => <div key={i} className="flex-1 rounded-t-lg bg-foreground/80" style={{ height: `${h}%`, background: i === 1 ? "hsl(var(--accent))" : undefined }} />)}</div>
              <p className="mt-3 text-xs text-muted-foreground">Source: Revenue · v2 · SUM(net_sales) · sales_transactions · example</p>
            </div>
          </div>
        </motion.div>
      </section>

      {/* FAQ */}
      <section className="container max-w-3xl py-20" id="faq">
        <motion.h2 {...fade} className="display text-center text-4xl sm:text-5xl">Frequently asked</motion.h2>
        <div className="mt-10 divide-y rounded-2xl border bg-card">
          {FAQ.map(([q, a], i) => (
            <div key={q}>
              <button className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left font-medium" aria-expanded={open === i} onClick={() => setOpen(open === i ? null : i)}>
                {q}<ChevronDown className={cn("h-4 w-4 shrink-0 transition-transform", open === i && "rotate-180")} />
              </button>
              {open === i && <p className="px-5 pb-5 text-sm text-muted-foreground">{a}</p>}
            </div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative overflow-hidden border-t">
        <SafeImage image={IMAGES.backgrounds.towers} className="absolute inset-0 h-full w-full" />
        <div className="absolute inset-0 bg-black/70" />
        <div className="container relative py-20 text-center text-white">
          <h2 className="display text-4xl sm:text-6xl">Stop arguing about the number.</h2>
          <p className="mx-auto mt-4 max-w-xl text-white/75">This is an academic capstone project. Create a workspace, or sign in with the demo accounts to see conflict detection, TARA and dashboards working on 62,000 rows of synthetic Indian retail data.</p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            <Link to="/register"><Button size="lg" className="bg-white text-black hover:bg-white/90">Get started</Button></Link>
            <Link to="/login"><Button size="lg" variant="outline" className="border-white/40 bg-transparent text-white hover:bg-white/10">Explore the demo</Button></Link>
          </div>
        </div>
      </section>
    </>
  );
}
