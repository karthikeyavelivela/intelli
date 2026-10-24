import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const cn = (...i: ClassValue[]) => twMerge(clsx(i));

export const RUPEE = "₹";
const EN_IN = "en-IN";

/** en-IN grouping (lakh / crore): 1245300 -> 12,45,300 */
export function numberIN(n: number, maxFrac = 2, minFrac = 0): string {
  return n.toLocaleString(EN_IN, { maximumFractionDigits: maxFrac, minimumFractionDigits: minFrac });
}

/** Rupee amount. Whole rupees from 1,000 up, paise below (mirrors the backend formatter). */
export function inr(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const frac = Math.abs(n) >= 1000 ? 0 : 2;
  const s = numberIN(Math.abs(n), frac, frac);
  return `${n < 0 ? "-" : ""}${RUPEE}${s}`;
}

/** 1,20,00,000 -> 1.2 Cr, 4,50,000 -> 45 L style compact form for KPI cards and chart axes. */
export function compactIN(n: number, currency = false): string {
  const a = Math.abs(n);
  const sign = n < 0 ? "-" : "";
  const p = currency ? RUPEE : "";
  const trim = (x: number) => String(Number(x.toFixed(2)));
  if (a >= 1e7) return `${sign}${p}${trim(a / 1e7)} Cr`;
  if (a >= 1e5) return `${sign}${p}${trim(a / 1e5)} L`;
  if (a >= 1e3) return `${sign}${p}${trim(a / 1e3)} K`;
  return `${sign}${p}${numberIN(a, 2)}`;
}

export function formatValue(v: unknown, unit?: string | null): string {
  if (v === null || v === undefined || v === "") return "—";
  const n = Number(v);
  if (typeof v === "string" && Number.isNaN(n)) return v;
  if (Number.isNaN(n)) return String(v);
  const u = (unit || "").toLowerCase();
  if (["inr", RUPEE, "rs", "currency"].includes(u)) return inr(n);
  if (["usd", "$"].includes(u)) return `$${numberIN(n, Math.abs(n) >= 1000 ? 0 : 2)}`;
  if (["percent", "%", "pct"].includes(u)) return `${numberIN(n, 1)}%`;
  return Number.isInteger(n) ? numberIN(n, 0) : numberIN(n, 2);
}

/** Axis / compact number formatting for a metric unit. */
export function axisFormat(unit?: string | null): (v: number) => string {
  const cur = ["inr", RUPEE, "rs", "currency"].includes((unit || "").toLowerCase());
  return (v: number) => compactIN(v, cur);
}

export const compact = (n: number) => compactIN(n);

export function formatBytes(b: number): string {
  if (!b) return "0 B";
  const u = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.min(u.length - 1, Math.floor(Math.log(b) / Math.log(1024)));
  return `${(b / 1024 ** i).toFixed(i ? 1 : 0)} ${u[i]}`;
}

const parseUtc = (iso: string) => new Date(/Z|[+-]\d\d:?\d\d$/.test(iso) ? iso : iso.replace(" ", "T") + "Z");

export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = parseUtc(iso).getTime();
  const s = Math.max(0, (Date.now() - d) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)}d ago`;
  return fmtDate(iso);
}

/** DD-MMM-YYYY in IST (timestamps from the API are UTC). */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = parseUtc(iso);
  const parts = new Intl.DateTimeFormat(EN_IN, { day: "2-digit", month: "short", year: "numeric", timeZone: "Asia/Kolkata" }).formatToParts(d);
  const g = (t: string) => parts.find((p) => p.type === t)?.value ?? "";
  return `${g("day")}-${g("month")}-${g("year")}`;
}

/** DD-MMM-YYYY HH:MM IST */
export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = parseUtc(iso);
  const t = new Intl.DateTimeFormat(EN_IN, { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" }).format(d);
  return `${fmtDate(iso)} ${t} IST`;
}

/** A pure calendar day (YYYY-MM-DD, no timezone shift) as DD-MMM-YYYY. */
export function fmtDay(day: string | null | undefined): string {
  if (!day) return "—";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(day);
  if (!m) return day;
  const mon = new Date(Date.UTC(+m[1], +m[2] - 1, 1)).toLocaleDateString(EN_IN, { month: "short", timeZone: "UTC" });
  return `${m[3]}-${mon}-${m[1]}`;
}

export const pct = (n: number | null | undefined, d = 0) => (n === null || n === undefined ? "—" : `${(n * 100).toFixed(d)}%`);
export const ms = (n: number | null | undefined) => (n === null || n === undefined ? "—" : n >= 1000 ? `${(n / 1000).toFixed(2)} s` : `${n.toFixed(n < 10 ? 1 : 0)} ms`);

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function toCsv(columns: string[], rows: unknown[][]): string {
  const esc = (v: unknown) => {
    const s = v === null || v === undefined ? "" : String(v);
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
  };
  return [columns.map(esc).join(","), ...rows.map((r) => r.map(esc).join(","))].join("\n");
}
