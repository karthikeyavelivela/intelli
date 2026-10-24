import { useState, type CSSProperties } from "react";
import { cn } from "@/lib/utils";
import type { Img } from "@/config/images";

interface Props {
  image: Img;
  className?: string;
  imgClassName?: string;
  eager?: boolean;
  /** keep colour (used for nothing by default; brand is strictly B/W) */
  color?: boolean;
  style?: CSSProperties;
  overlay?: boolean;
}

/** Remote photo with skeleton placeholder, lazy loading, alt text, B/W treatment and a local gradient fallback on error. */
export function SafeImage({ image, className, imgClassName, eager, color, style, overlay }: Props) {
  const [state, setState] = useState<"loading" | "ok" | "error">("loading");
  return (
    <div className={cn("relative overflow-hidden bg-muted", className)} style={style}>
      {state !== "ok" && (
        <div
          className={cn("absolute inset-0", state === "loading" ? "skeleton rounded-none" : "")}
          style={state === "error" ? { background: "linear-gradient(135deg, hsl(var(--muted)) 0%, hsl(var(--border)) 55%, hsl(var(--muted-foreground) / .35) 100%)" } : undefined}
          role={state === "error" ? "img" : undefined}
          aria-label={state === "error" ? image.alt : undefined}
          data-fallback={state === "error" ? "true" : undefined}
        />
      )}
      {state !== "error" && (
        <img
          src={image.url}
          alt={image.alt}
          loading={eager ? "eager" : "lazy"}
          decoding="async"
          referrerPolicy="no-referrer"
          onLoad={() => setState("ok")}
          onError={() => setState("error")}
          className={cn("h-full w-full object-cover transition-opacity duration-700", !color && "bw-img", state === "ok" ? "opacity-100" : "opacity-0", imgClassName)}
        />
      )}
      {overlay && <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/60 via-black/10 to-transparent" />}
    </div>
  );
}
