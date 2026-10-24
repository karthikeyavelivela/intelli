import { motion } from "framer-motion";
import { AlertTriangle, ArrowRight, CheckCircle2, KeyRound, ShieldCheck } from "lucide-react";
import { useState, type FormEvent, type ReactNode } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { Logo } from "@/components/common";
import { SafeImage } from "@/components/SafeImage";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { IMAGES, type Img } from "@/config/images";

function AuthFrame({ image, quote, children }: { image: Img; quote: string; children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <div className="relative hidden lg:block">
        <SafeImage image={image} className="absolute inset-0 h-full w-full" eager overlay />
        <div className="absolute inset-0 flex flex-col justify-between p-10 text-white">
          <Link to="/" className="inline-flex items-center gap-2 font-semibold"><span className="rounded-lg bg-white p-1"><svg viewBox="0 0 32 32" className="h-6 w-6"><rect width="32" height="32" rx="8" fill="#0a0a0a" /><path d="M8 22V10l8 8 8-8v12" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" /><circle cx="24" cy="9" r="2.4" fill="#8b7cf6" /></svg></span>IntelliMetrics AI</Link>
          <div>
            <p className="display max-w-md text-4xl leading-tight">{quote}</p>
            <p className="mt-4 text-sm text-white/70">TARA answers from governed definitions. Never from guesses.</p>
          </div>
        </div>
      </div>
      <div className="relative flex flex-col px-5 py-6 sm:px-10">
        <div className="flex items-center justify-between">
          <Link to="/" className="lg:invisible"><Logo /></Link>
          <ThemeToggle />
        </div>
        <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.35 }} className="mx-auto flex w-full max-w-md flex-1 flex-col justify-center py-10">
          {children}
        </motion.div>
      </div>
    </div>
  );
}

const DEMOS = [
  { label: "Admin", email: "admin@intellimetrics.demo", password: "Admin@12345", note: "Everything, incl. users & audit" },
  { label: "Data Analyst", email: "analyst@intellimetrics.demo", password: "Analyst@12345", note: "Datasets, metrics, TARA generator, Lab" },
  { label: "Business User", email: "business@intellimetrics.demo", password: "Business@12345", note: "Ask TARA & dashboards" },
  { label: "Reviewer", email: "reviewer@intellimetrics.demo", password: "Reviewer@12345", note: "Approve, publish, resolve conflicts" },
  { label: "Other workspace admin", email: "admin@sagarfoods.demo", password: "Admin@12345", note: "Sagar Foods & Beverages Ltd: isolation demo" },
];

export function Login() {
  const { user, login } = useAuth();
  const nav = useNavigate();
  const loc = useLocation() as any;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to={loc.state?.from || "/app/dashboard"} replace />;
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      await login(email.trim(), password);
      nav(loc.state?.from || "/app/dashboard", { replace: true });
    } catch (ex) {
      setErr(ex instanceof ApiError ? ex.message : "Could not sign in");
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthFrame image={IMAGES.auth.login} quote="One definition of revenue. For everyone, everywhere.">
      <h1 className="text-3xl font-semibold tracking-tight">Welcome back</h1>
      <p className="mt-1.5 text-muted-foreground">Sign in to your IntelliMetrics workspace.</p>
      <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
        <Field label="Email">{(id) => <Input id={id} name="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.com" required data-testid="login-email" />}</Field>
        <Field label="Password">{(id) => <Input id={id} name="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required data-testid="login-password" />}</Field>
        {err && <p role="alert" className="flex items-center gap-2 rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger"><AlertTriangle className="h-4 w-4" />{err}</p>}
        <Button type="submit" size="lg" className="w-full" loading={busy} data-testid="login-submit">Sign in <ArrowRight className="h-4 w-4" /></Button>
        <div className="flex justify-between text-sm"><Link to="/forgot-password" className="text-muted-foreground hover:text-foreground">Forgot password?</Link><Link to="/register" className="font-medium text-accent hover:underline">Create a workspace</Link></div>
      </form>
      <section className="mt-8 rounded-2xl border border-dashed bg-muted/40 p-4" aria-label="Demo accounts">
        <div className="mb-3 flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold"><KeyRound className="h-4 w-4 text-accent" />Demo accounts</h2><span className="rounded-full border border-accent/30 bg-accent/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-accent">DEMO</span></div>
        <div className="grid gap-1.5">
          {DEMOS.map((d) => (
            <button key={d.email} type="button" onClick={() => { setEmail(d.email); setPassword(d.password); setErr(null); }} data-testid={`demo-${d.label.toLowerCase().replace(/\s+/g, "-")}`}
              className="flex items-center justify-between rounded-xl border bg-card px-3 py-2 text-left text-sm transition-colors hover:border-accent hover:bg-accent/5">
              <span><span className="font-medium">{d.label}</span><span className="block text-xs text-muted-foreground">{d.note}</span></span>
              <span className="hidden font-mono text-[11px] text-muted-foreground sm:block">{d.email.split("@")[0]}</span>
            </button>
          ))}
        </div>
        <p className="mt-2 text-xs text-muted-foreground">Click an account to fill the form, then press Sign in. University project: all data is synthetic.</p>
      </section>
    </AuthFrame>
  );
}

export function Register() {
  const { user, setUser } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ name: "", email: "", password: "", workspace_name: "" });
  const [err, setErr] = useState<string | null>(null);
  const [fieldErr, setFieldErr] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  if (user) return <Navigate to="/app/dashboard" replace />;
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(null); setFieldErr({}); setBusy(true);
    try {
      const r = await api.post("/auth/register", f);
      setUser(r.user);
      nav("/app/dashboard", { replace: true });
    } catch (ex) {
      if (ex instanceof ApiError) {
        if (ex.code === "validation_error" && Array.isArray(ex.details)) setFieldErr(Object.fromEntries(ex.details.map((d: any) => [d.field, d.message])));
        setErr(ex.message);
      }
    } finally { setBusy(false); }
  };
  return (
    <AuthFrame image={IMAGES.auth.register} quote="Start with one governed metric. End with a company that trusts its numbers.">
      <h1 className="text-3xl font-semibold tracking-tight">Create your workspace</h1>
      <p className="mt-1.5 text-muted-foreground">You'll be the workspace admin. Invite your team afterwards.</p>
      <form onSubmit={submit} className="mt-8 space-y-4" noValidate>
        <Field label="Your name" error={fieldErr.name}>{(id) => <Input id={id} value={f.name} onChange={set("name")} autoComplete="name" required data-testid="reg-name" />}</Field>
        <Field label="Work email" error={fieldErr.email}>{(id) => <Input id={id} type="email" value={f.email} onChange={set("email")} autoComplete="email" required data-testid="reg-email" />}</Field>
        <Field label="Workspace name" error={fieldErr.workspace_name}>{(id) => <Input id={id} value={f.workspace_name} onChange={set("workspace_name")} placeholder="Acme Analytics" required data-testid="reg-workspace" />}</Field>
        <Field label="Password" hint="At least 8 characters with letters and digits." error={fieldErr.password}>{(id) => <Input id={id} type="password" value={f.password} onChange={set("password")} autoComplete="new-password" required data-testid="reg-password" />}</Field>
        {err && !Object.keys(fieldErr).length && <p role="alert" className="rounded-xl border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">{err}</p>}
        <Button type="submit" size="lg" className="w-full" loading={busy} data-testid="reg-submit">Create workspace</Button>
        <p className="text-center text-sm text-muted-foreground">Already have an account? <Link to="/login" className="font-medium text-accent hover:underline">Sign in</Link></p>
      </form>
    </AuthFrame>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState<{ link?: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { const r = await api.post("/auth/forgot-password", { email }); setDone({ link: r.dev_reset_link }); }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : "Request failed"); }
    finally { setBusy(false); }
  };
  return (
    <AuthFrame image={IMAGES.auth.forgot} quote="Locked out? It happens to the best analysts.">
      <h1 className="text-3xl font-semibold tracking-tight">Reset your password</h1>
      <p className="mt-1.5 text-muted-foreground">Enter your email and we'll send a reset link.</p>
      {done ? (
        <div className="mt-8 space-y-4" role="status">
          <p className="flex items-start gap-2 rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success"><CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />If that email exists, a reset link has been sent.</p>
          {done.link && (
            <div className="rounded-xl border border-dashed border-warning/50 bg-warning/10 p-3 text-sm" data-testid="dev-reset-banner">
              <p className="mb-1 font-semibold text-warning">Development mode: no email provider configured</p>
              <p className="text-muted-foreground">The reset link is printed in the backend logs and shown here only because ENV=development:</p>
              <Link to={(() => { try { const u = new URL(done.link!); return u.pathname + u.search; } catch { return done.link!; } })()} className="mt-2 block break-all font-mono text-xs text-accent underline" data-testid="dev-reset-link">{done.link}</Link>
            </div>
          )}
          <Link to="/login" className="inline-block text-sm text-accent hover:underline">Back to sign in</Link>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-8 space-y-4">
          <Field label="Email">{(id) => <Input id={id} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required data-testid="forgot-email" />}</Field>
          {err && <p role="alert" className="text-sm text-danger">{err}</p>}
          <Button type="submit" size="lg" className="w-full" loading={busy} data-testid="forgot-submit">Send reset link</Button>
          <Link to="/login" className="block text-center text-sm text-muted-foreground hover:text-foreground">Back to sign in</Link>
        </form>
      )}
    </AuthFrame>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") || "";
  const nav = useNavigate();
  const [pw, setPw] = useState("");
  const [pw2, setPw2] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    if (pw !== pw2) return setErr("Passwords do not match");
    setBusy(true);
    try { await api.post("/auth/reset-password", { token, password: pw }); setOk(true); setTimeout(() => nav("/login"), 1800); }
    catch (ex) { setErr(ex instanceof ApiError ? ex.message : "Could not reset password"); }
    finally { setBusy(false); }
  };
  return (
    <AuthFrame image={IMAGES.auth.forgot} quote="A fresh start, securely.">
      <h1 className="text-3xl font-semibold tracking-tight">Choose a new password</h1>
      {!token ? <p className="mt-4 text-danger" role="alert">This reset link is missing its token. Request a new one.</p> : ok ? (
        <p className="mt-6 flex items-center gap-2 rounded-xl border border-success/30 bg-success/10 p-3 text-sm text-success" role="status"><ShieldCheck className="h-4 w-4" />Password updated. Redirecting to sign in…</p>
      ) : (
        <form onSubmit={submit} className="mt-8 space-y-4">
          <Field label="New password" hint="At least 8 characters with letters and digits.">{(id) => <Input id={id} type="password" value={pw} onChange={(e) => setPw(e.target.value)} autoComplete="new-password" required data-testid="reset-password" />}</Field>
          <Field label="Confirm password">{(id) => <Input id={id} type="password" value={pw2} onChange={(e) => setPw2(e.target.value)} autoComplete="new-password" required data-testid="reset-password2" />}</Field>
          {err && <p role="alert" className="text-sm text-danger">{err}</p>}
          <Button type="submit" size="lg" className="w-full" loading={busy} data-testid="reset-submit">Update password</Button>
        </form>
      )}
    </AuthFrame>
  );
}
