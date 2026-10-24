import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme, type ThemeChoice } from "@/lib/theme";
import { cn } from "@/lib/utils";

const OPTS: { v: ThemeChoice; label: string; Icon: typeof Sun }[] = [
  { v: "light", label: "Light", Icon: Sun },
  { v: "dark", label: "Dark", Icon: Moon },
  { v: "system", label: "System", Icon: Monitor },
];

/** Three-way Light / Dark / System segmented control. */
export function ThemeToggle({ className, compact }: { className?: string; compact?: boolean }) {
  const { theme, setTheme } = useTheme();
  return (
    <div role="radiogroup" aria-label="Theme" className={cn("inline-flex items-center rounded-full border bg-muted p-0.5", className)} data-testid="theme-toggle">
      {OPTS.map(({ v, label, Icon }) => (
        <button
          key={v}
          role="radio"
          aria-checked={theme === v}
          aria-label={`${label} theme`}
          title={`${label} theme`}
          data-theme-option={v}
          onClick={() => setTheme(v)}
          className={cn("flex h-7 items-center justify-center gap-1.5 rounded-full px-2 text-xs font-medium transition-colors", theme === v ? "bg-card text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground", compact ? "w-7 px-0" : "")}
        >
          <Icon className="h-3.5 w-3.5" aria-hidden />
          {!compact && <span className="hidden lg:inline">{label}</span>}
        </button>
      ))}
    </div>
  );
}
