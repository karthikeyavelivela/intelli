import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/common";
import { ThemeToggle } from "@/components/ThemeToggle";

function Shell({ code, title, text, inApp }: { code: string; title: string; text: string; inApp?: boolean }) {
  return (
    <div className={inApp ? "flex min-h-[60vh] items-center justify-center" : "relative flex min-h-screen items-center justify-center overflow-hidden px-4"}>
      {!inApp && <div className="grid-bg absolute inset-0 -z-10 opacity-60" aria-hidden />}
      {!inApp && <div className="absolute right-4 top-4"><ThemeToggle /></div>}
      <div className="text-center">
        {!inApp && <Link to="/" className="mb-10 inline-block"><Logo /></Link>}
        <p className="display text-8xl text-muted-foreground/60 sm:text-9xl" aria-hidden>{code}</p>
        <h1 className="mt-2 text-2xl font-semibold">{title}</h1>
        <p className="mx-auto mt-2 max-w-md text-muted-foreground">{text}</p>
        <div className="mt-6 flex justify-center gap-2">
          <Button onClick={() => history.back()} variant="outline">Go back</Button>
          <Link to={inApp ? "/app/dashboard" : "/"}><Button>{inApp ? "Dashboard" : "Home"}</Button></Link>
        </div>
      </div>
    </div>
  );
}
export const NotFound = ({ inApp }: { inApp?: boolean }) => <Shell code="404" title="Page not found" text="The page you're looking for doesn't exist or has moved." inApp={inApp} />;
export const Forbidden = () => <Shell code="403" title="You don't have access" text="Your role doesn't include permission for this area. Ask a workspace admin if you need it." />;
