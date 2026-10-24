import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

type Kind = "success" | "error" | "info";
interface Toast { id: number; kind: Kind; title: string; description?: string }
interface Ctx { toast: (t: Omit<Toast, "id">) => void; success: (title: string, description?: string) => void; error: (title: string, description?: string) => void }
const ToastCtx = createContext<Ctx>({ toast() {}, success() {}, error() {} });
let n = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const dismiss = (id: number) => setItems((l) => l.filter((t) => t.id !== id));
  const toast = useCallback((t: Omit<Toast, "id">) => {
    const id = ++n;
    setItems((l) => [...l.slice(-3), { ...t, id }]);
    setTimeout(() => dismiss(id), t.kind === "error" ? 7000 : 4000);
  }, []);
  const value = useMemo(() => ({ toast, success: (title: string, description?: string) => toast({ kind: "success", title, description }), error: (title: string, description?: string) => toast({ kind: "error", title, description }) }), [toast]);
  const Icon = { success: CheckCircle2, error: AlertTriangle, info: Info };
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[60] flex w-[calc(100vw-2rem)] max-w-sm flex-col gap-2" role="region" aria-label="Notifications" aria-live="polite">
        <AnimatePresence>
          {items.map((t) => {
            const I = Icon[t.kind];
            return (
              <motion.div key={t.id} initial={{ opacity: 0, y: 12, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, x: 24 }}
                className="pointer-events-auto flex items-start gap-3 rounded-xl border bg-card p-3.5 shadow-lift">
                <I className={cn("mt-0.5 h-4 w-4 shrink-0", t.kind === "success" && "text-success", t.kind === "error" && "text-danger", t.kind === "info" && "text-accent")} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">{t.title}</p>
                  {t.description && <p className="mt-0.5 break-words text-xs text-muted-foreground">{t.description}</p>}
                </div>
                <button onClick={() => dismiss(t.id)} aria-label="Dismiss" className="rounded p-0.5 hover:bg-muted"><X className="h-3.5 w-3.5" /></button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>
    </ToastCtx.Provider>
  );
}
export const useToast = () => useContext(ToastCtx);
