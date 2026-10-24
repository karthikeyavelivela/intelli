import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { axisFormat, compact, fmtDay, formatValue } from "@/lib/utils";

/** Grayscale-first palette with the single accent; values are CSS variables so charts follow the theme. */
export const SERIES = ["hsl(var(--chart-1))", "hsl(var(--chart-2))", "hsl(var(--chart-3))", "hsl(var(--chart-4))", "hsl(var(--chart-5))"];

export interface Point { x: string; y: number | null }

const MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const isDay = (v: string) => /^\d{4}-\d{2}-\d{2}/.test(v);
/** Axis tick: dates as Mon-YY (e.g. Apr-26); long category names truncated. */
function tickLabel(v: string): string {
  if (isDay(v)) return `${MON[Number(v.slice(5, 7)) - 1]}-${v.slice(2, 4)}`;
  return v.length > 14 ? v.slice(0, 13) + "…" : v;
}
const tipLabel = (v: string) => (isDay(v) ? fmtDay(v) : v);

const tooltipStyle = { background: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 12, fontSize: 12, boxShadow: "0 8px 24px -12px rgb(0 0 0 / .3)" };

export function SeriesChart({ type, data, unit, height = 260, name = "Value" }: { type: "line" | "bar" | "pie" | "area"; data: Point[]; unit?: string | null; height?: number; name?: string }) {
  const rows = data.map((d) => ({ ...d, y: d.y ?? 0 }));
  const fmt = (v: number) => formatValue(v, unit);
  const axis = { stroke: "hsl(var(--muted-foreground))", fontSize: 11, tickLine: false, axisLine: false } as const;
  if (type === "pie") {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart role="img" aria-label={`${name} breakdown pie chart`}>
          <Pie data={rows} dataKey="y" nameKey="x" innerRadius="52%" outerRadius="82%" paddingAngle={2} stroke="hsl(var(--card))" strokeWidth={2}>
            {rows.map((_, i) => <Cell key={i} fill={SERIES[i % SERIES.length]} />)}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => fmt(v)} />
          <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    );
  }
  const common = { data: rows, margin: { top: 8, right: 12, left: 0, bottom: 0 } };
  return (
    <ResponsiveContainer width="100%" height={height}>
      {type === "bar" ? (
        <BarChart {...common} role="img" aria-label={`${name} bar chart`}>
          <CartesianGrid vertical={false} stroke="hsl(var(--grid))" />
          <XAxis dataKey="x" tickFormatter={tickLabel} {...axis} interval="preserveStartEnd" />
          <YAxis tickFormatter={axisFormat(unit)} width={62} {...axis} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={tipLabel} formatter={(v: number) => [fmt(v), name]} cursor={{ fill: "hsl(var(--muted))" }} />
          <Bar dataKey="y" radius={[6, 6, 0, 0]} maxBarSize={48}>
            {rows.map((_, i) => <Cell key={i} fill={i === 0 ? "hsl(var(--chart-1))" : "hsl(var(--chart-2))"} />)}
          </Bar>
        </BarChart>
      ) : type === "area" ? (
        <AreaChart {...common} role="img" aria-label={`${name} area chart`}>
          <defs>
            <linearGradient id="areaFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity={0.35} />
              <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid vertical={false} stroke="hsl(var(--grid))" />
          <XAxis dataKey="x" tickFormatter={tickLabel} {...axis} interval="preserveStartEnd" />
          <YAxis tickFormatter={axisFormat(unit)} width={62} {...axis} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={tipLabel} formatter={(v: number) => [fmt(v), name]} />
          <Area type="monotone" dataKey="y" stroke="hsl(var(--chart-1))" strokeWidth={2.2} fill="url(#areaFill)" />
        </AreaChart>
      ) : (
        <LineChart {...common} role="img" aria-label={`${name} line chart`}>
          <CartesianGrid vertical={false} stroke="hsl(var(--grid))" />
          <XAxis dataKey="x" tickFormatter={tickLabel} {...axis} interval="preserveStartEnd" />
          <YAxis tickFormatter={axisFormat(unit)} width={62} {...axis} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={tipLabel} formatter={(v: number) => [fmt(v), name]} />
          <Line type="monotone" dataKey="y" stroke="hsl(var(--chart-1))" strokeWidth={2.4} dot={rows.length < 20 ? { r: 3, fill: "hsl(var(--card))", strokeWidth: 2 } : false} activeDot={{ r: 5 }} />
        </LineChart>
      )}
    </ResponsiveContainer>
  );
}

export function MultiBar({ data, keys, height = 240 }: { data: Record<string, any>[]; keys: { key: string; label: string }[]; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--grid))" />
        <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} width={40} domain={[0, 1]} tickFormatter={(v) => `${Math.round(v * 100)}%`} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => `${(v * 100).toFixed(1)}%`} cursor={{ fill: "hsl(var(--muted))" }} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        {keys.map((k, i) => <Bar key={k.key} dataKey={k.key} name={k.label} fill={SERIES[i]} radius={[6, 6, 0, 0]} maxBarSize={36} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function TrendLines({ data, keys, height = 240, percent }: { data: Record<string, any>[]; keys: { key: string; label: string }[]; height?: number; percent?: boolean }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid vertical={false} stroke="hsl(var(--grid))" />
        <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} width={44} tickFormatter={(v) => (percent ? `${Math.round(v * 100)}%` : compact(v))} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => (percent ? `${(v * 100).toFixed(1)}%` : v)} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        {keys.map((k, i) => <Line key={k.key} type="monotone" dataKey={k.key} name={k.label} stroke={SERIES[i]} strokeWidth={2} dot={{ r: 2.5 }} />)}
      </LineChart>
    </ResponsiveContainer>
  );
}

/** Grouped bars: one cluster per x (e.g. region) and one bar per series (e.g. payment method). */
export function GroupedBars({ data, series, unit, height = 280 }: { data: Record<string, any>[]; series: string[]; unit?: string | null; height?: number }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }} role="img" aria-label="Grouped bar chart">
        <CartesianGrid vertical={false} stroke="hsl(var(--grid))" />
        <XAxis dataKey="x" stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <YAxis tickFormatter={axisFormat(unit)} width={52} stroke="hsl(var(--muted-foreground))" fontSize={11} tickLine={false} axisLine={false} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => formatValue(v, unit)} cursor={{ fill: "hsl(var(--muted))" }} />
        <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
        {series.map((k, i) => <Bar key={k} dataKey={k} name={k} fill={SERIES[i % SERIES.length]} radius={[6, 6, 0, 0]} maxBarSize={34} />)}
      </BarChart>
    </ResponsiveContainer>
  );
}
