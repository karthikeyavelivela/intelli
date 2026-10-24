import * as M from "@radix-ui/react-dropdown-menu";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export const Menu = M.Root;
export const MenuTrigger = M.Trigger;
export const MenuSeparator = () => <M.Separator className="my-1 h-px bg-border" />;
export const MenuLabel = ({ className, ...p }: ComponentProps<typeof M.Label>) => <M.Label className={cn("px-2.5 py-1.5 text-xs text-muted-foreground", className)} {...p} />;
export const MenuContent = ({ className, ...p }: ComponentProps<typeof M.Content>) => (
  <M.Portal>
    <M.Content align="end" sideOffset={8} className={cn("z-50 min-w-[210px] rounded-xl border bg-card p-1.5 shadow-lift animate-fade-up", className)} {...p} />
  </M.Portal>
);
export const MenuItem = ({ className, ...p }: ComponentProps<typeof M.Item>) => (
  <M.Item className={cn("flex cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-sm outline-none data-[highlighted]:bg-muted", className)} {...p} />
);
