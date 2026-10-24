import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { Skeleton, Spinner } from "@/components/ui/misc";
import { useAuth } from "@/lib/auth";

export function RequireAuth() {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center" role="status" aria-label="Loading session">
        <div className="space-y-3 text-center"><Spinner className="mx-auto h-6 w-6" /><Skeleton className="mx-auto h-3 w-32" /></div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" state={{ from: loc.pathname + loc.search }} replace />;
  return <Outlet />;
}

/** Frontend RBAC gate. The backend independently enforces every endpoint. */
export function RequireCap({ cap, children }: { cap: string; children: ReactNode }) {
  const { can } = useAuth();
  if (!can(cap)) return <Navigate to="/403" replace />;
  return <>{children}</>;
}
