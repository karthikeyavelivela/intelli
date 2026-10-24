import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowRight, BookOpenCheck, Database, FlaskConical, GitCompare, History, LayoutGrid, Sparkles } from "lucide-react";
import { SafeImage } from "@/components/SafeImage";
import { Button } from "@/components/ui/button";
import { IMAGES } from "@/config/images";

const STEPS = [
  { icon: Database, t: "1 · Datasets", d: "Upload CSV, Excel, JSON or Parquet (the demo uses synthetic Indian retail data), or connect PostgreSQL/MySQL read-only. Celery workers convert to Parquet, detect the schema, and profile nulls and duplicates while you watch a progress bar.", img: IMAGES.features.datasets },
  { icon: BookOpenCheck, t: "2 · Semantic layer", d: "Define metrics with a formula, filters, unit, owner and department. Submit, approve, publish. Exactly one live definition per governed metric.", img: IMAGES.features.metrics },
  { icon: Sparkles, t: "3 · TARA generator", d: "Describe a metric in plain English. TARA grounds the answer in your schema and catalog, validates it, and hands you an editable draft, never an auto-published metric.", img: IMAGES.features.tara },
  { icon: GitCompare, t: "4 · Conflict center", d: "Structural comparison across departments finds differing formulas, aggregations, filters, units, date ranges and datasets. Assign, review, approve and resolve with a full audit trail.", img: IMAGES.features.conflicts },
  { icon: FlaskConical, t: "5 · Formula Lab", d: "Write expressions in a restricted grammar. A real parser and AST compile to parameterized DuckDB SQL with timeouts and row limits.", img: IMAGES.features.formula },
  { icon: History, t: "6 · Version control", d: "Immutable versions, side-by-side diffs and rollback-as-new-version. Dashboards follow the latest published definition or a version you pin.", img: IMAGES.features.versions },
  { icon: LayoutGrid, t: "7 · Dashboards & reports", d: "Drag-and-drop dashboards backed by live API data, with PNG/PDF/CSV export plus CSV/Excel/PDF reports.", img: IMAGES.features.dashboards },
];

export default function About() {
  return (
    <>
      <section className="relative overflow-hidden border-b">
        <SafeImage image={IMAGES.about.office} className="absolute inset-0 h-full w-full" eager />
        <div className="absolute inset-0 bg-background/85 dark:bg-background/88" />
        <div className="container relative py-20 text-center">
          <p className="eyebrow">Product tour · University project</p>
          <h1 className="display mx-auto mt-3 max-w-3xl text-5xl sm:text-6xl">How IntelliMetrics keeps every number honest</h1>
          <p className="mx-auto mt-5 max-w-2xl text-lg text-muted-foreground">A walk through the platform, from raw files to a board-ready dashboard.</p>
        </div>
      </section>
      <section className="container pt-16" aria-labelledby="about-project">
        <div className="card p-8 md:p-10" data-testid="about-project">
          <p className="eyebrow">About this project</p>
          <h2 id="about-project" className="display mt-2 text-4xl">An academic capstone, not a commercial product</h2>
          <p className="mt-4 max-w-3xl text-muted-foreground">IntelliMetrics AI is a university capstone project by <b className="text-foreground">Devi Priya, Priyanka, Akshay and Bhaskar</b>, guided by <b className="text-foreground">Dr. Asesh Kumar Tripathy</b>, KL University, academic year 2026-27. It studies how a governed semantic layer plus a carefully constrained AI assistant can remove the "which revenue is the real revenue?" problem.</p>
          <p className="mt-3 max-w-3xl text-muted-foreground">All organisations, people, phone numbers and transactions in the demo (Bharat Retail Pvt Ltd, Sagar Foods &amp; Beverages Ltd) are <b className="text-foreground">synthetic demonstration data</b>. Amounts are in Indian rupees, the financial year runs April to March, and times are shown in IST.</p>
        </div>
      </section>
      <section className="container space-y-6 py-16">
        {STEPS.map((s, i) => (
          <motion.article key={s.t} initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: "-60px" }} className={`card grid overflow-hidden md:grid-cols-2 ${i % 2 ? "md:[&>div:first-child]:order-2" : ""}`}>
            <SafeImage image={s.img} className="min-h-[220px]" />
            <div className="flex flex-col justify-center p-8">
              <s.icon className="mb-3 h-6 w-6 text-accent" aria-hidden />
              <h2 className="text-xl font-semibold">{s.t}</h2>
              <p className="mt-2 text-muted-foreground">{s.d}</p>
            </div>
          </motion.article>
        ))}
      </section>
      <section className="border-t bg-muted/40 py-16">
        <div className="container grid items-center gap-10 md:grid-cols-2">
          <SafeImage image={IMAGES.about.team} className="aspect-[4/3] rounded-3xl border" />
          <div>
            <p className="eyebrow">Built for teams</p>
            <h2 className="display mt-3 text-4xl">Four roles. One source of truth.</h2>
            <p className="mt-3 text-muted-foreground">Admins govern, Data Analysts build, Reviewers approve and Business Users ask. Workspaces are fully isolated, every sensitive action is audited, and permissions are enforced on every endpoint.</p>
            <Link to="/login" className="mt-6 inline-block"><Button>Explore the demo <ArrowRight className="h-4 w-4" /></Button></Link>
          </div>
        </div>
      </section>
    </>
  );
}
