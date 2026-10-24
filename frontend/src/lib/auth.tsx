import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, setAuthLostHandler } from "./api";

export interface User {
  id: string; email: string; name: string; role: string; role_label: string;
  workspace: { id: string; name: string; is_demo: boolean; slug: string };
  capabilities: string[]; is_demo: boolean; title?: string | null; avatar_url?: string | null; last_login?: string | null; created_at: string;
}
interface AuthCtx {
  user: User | null; loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (u: User | null) => void;
  can: (cap: string) => boolean;
}
const Ctx = createContext<AuthCtx>(null as any);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();

  useEffect(() => {
    setAuthLostHandler(() => { setUser(null); qc.clear(); });
    api.get("/auth/me").then((r) => setUser(r.user)).catch(() => setUser(null)).finally(() => setLoading(false));
  }, [qc]);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.post("/auth/login", { email, password });
    qc.clear();
    setUser(r.user);
    return r.user as User;
  }, [qc]);

  const logout = useCallback(async () => {
    try { await api.post("/auth/logout"); } catch { /* already out */ }
    setUser(null);
    qc.clear();
  }, [qc]);

  const value = useMemo<AuthCtx>(() => ({ user, loading, login, logout, setUser, can: (c) => !!user?.capabilities.includes(c) }), [user, loading, login, logout]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAuth = () => useContext(Ctx);
export const useCan = (cap: string) => useAuth().can(cap);
