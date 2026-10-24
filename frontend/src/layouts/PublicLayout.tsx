import { Menu, X } from "lucide-react";
import { useState } from "react";
import { Link, NavLink, Outlet } from "react-router-dom";
import { Logo } from "@/components/common";
import { ThemeToggle } from "@/components/ThemeToggle";
import { Button } from "@/components/ui/button";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const LINKS = [
  { to: "/", label: "Product", end: true },
  { to: "/about", label: "About this project" },
  { to: "/#faq", label: "FAQ" },
];

export function PublicLayout() {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-xl">
        <div className="container flex h-16 items-center justify-between">
          <Link to="/" aria-label="IntelliMetrics AI home"><Logo /></Link>
          <nav aria-label="Main" className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <NavLink key={l.to} to={l.to} end={l.end} className={({ isActive }) => cn("rounded-lg px-3 py-2 text-sm text-muted-foreground transition-colors hover:text-foreground", isActive && !l.to.includes("#") && "text-foreground")}>{l.label}</NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-2">
            <ThemeToggle />
            {user ? (
              <Link to="/app/dashboard"><Button size="sm">Open app</Button></Link>
            ) : (
              <>
                <Link to="/login" className="hidden sm:block"><Button variant="ghost" size="sm" data-testid="nav-signin">Sign in</Button></Link>
                <Link to="/register"><Button size="sm">Get started</Button></Link>
              </>
            )}
            <Button variant="ghost" size="icon" className="md:hidden" aria-label="Toggle menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>{open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}</Button>
          </div>
        </div>
        {open && (
          <div className="border-t bg-background md:hidden">
            <nav className="container flex flex-col py-3" aria-label="Mobile">
              {LINKS.map((l) => <Link key={l.to} to={l.to} onClick={() => setOpen(false)} className="rounded-lg px-2 py-3 text-sm hover:bg-muted">{l.label}</Link>)}
              <Link to="/login" onClick={() => setOpen(false)} className="rounded-lg px-2 py-3 text-sm hover:bg-muted">Sign in</Link>
            </nav>
          </div>
        )}
      </header>
      <main className="flex-1"><Outlet /></main>
      <footer className="border-t">
        <div className="container grid gap-10 py-12 md:grid-cols-4">
          <div className="md:col-span-2">
            <Logo />
            <p className="mt-3 max-w-sm text-sm text-muted-foreground">One governed definition for every business metric. Meet TARA, the analyst that never invents a number. A university project built around an Indian retail case study.</p>
          </div>
          <div>
            <h4 className="mb-3 text-sm font-semibold">Product</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li><Link className="hover:text-foreground" to="/about">About this project</Link></li>
              <li><Link className="hover:text-foreground" to="/login">Sign in</Link></li>
              <li><Link className="hover:text-foreground" to="/register">Get started</Link></li>
              <li><a className="hover:text-foreground" href="/docs">API docs</a></li>
            </ul>
          </div>
          <div>
            <h4 className="mb-3 text-sm font-semibold">Governance</h4>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>Semantic layer</li><li>Conflict detection</li><li>Version control</li><li>Audit trail</li>
            </ul>
          </div>
        </div>
        <div className="border-t py-5 text-center text-xs text-muted-foreground"><span data-testid="university-note">University project (academic capstone, KL University). All data is synthetic demonstration data. Photography via Unsplash and Pexels.</span></div>
      </footer>
    </div>
  );
}
