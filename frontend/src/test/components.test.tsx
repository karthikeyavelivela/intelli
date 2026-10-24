import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { DataTable, EmptyState, FormulaDiff, Pager } from "@/components/common";
import { SafeImage } from "@/components/SafeImage";
import { ThemeToggle } from "@/components/ThemeToggle";
import { StatusBadge } from "@/components/ui/badge";
import { ValidationPanel } from "@/components/MetricForm";
import { RequireCap } from "@/layouts/guards";
import { ThemeProvider } from "@/lib/theme";
import { axisFormat, compact, compactIN, fmtDate, fmtDateTime, fmtDay, formatBytes, formatValue, toCsv } from "@/lib/utils";
import { IMAGES } from "@/config/images";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ can: (c: string) => c === "chat.ask", user: { name: "T" } }) }));

describe("ThemeToggle", () => {
  it("switches theme, persists the choice and toggles the dark class", async () => {
    localStorage.clear();
    render(<ThemeProvider><ThemeToggle /></ThemeProvider>);
    const user = userEvent.setup();
    await user.click(screen.getByRole("radio", { name: "Dark theme" }));
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("im-theme")).toBe("dark");
    expect(screen.getByRole("radio", { name: "Dark theme" })).toHaveAttribute("aria-checked", "true");
    await user.click(screen.getByRole("radio", { name: "Light theme" }));
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    await user.click(screen.getByRole("radio", { name: "System theme" }));
    expect(localStorage.getItem("im-theme")).toBe("system");
  });
});

describe("SafeImage", () => {
  it("has alt text, lazy loading, B/W treatment and falls back to a gradient on error", () => {
    render(<SafeImage image={IMAGES.hero.main} />);
    const img = screen.getByAltText(IMAGES.hero.main.alt) as HTMLImageElement;
    expect(img).toHaveAttribute("loading", "lazy");
    expect(img.className).toContain("bw-img");
    fireEvent.error(img);
    expect(screen.queryByAltText(IMAGES.hero.main.alt)).toBeNull();
    expect(screen.getByRole("img", { name: IMAGES.hero.main.alt })).toHaveAttribute("data-fallback", "true");
  });
  it("reveals the image once loaded", () => {
    render(<SafeImage image={IMAGES.hero.dashboard} eager />);
    const img = screen.getByAltText(IMAGES.hero.dashboard.alt);
    expect(img).toHaveAttribute("loading", "eager");
    fireEvent.load(img);
    expect(img.className).toContain("opacity-100");
  });
});

describe("image config", () => {
  it("every image has a URL, alt text and a source", () => {
    const all = Object.values(IMAGES).flatMap((g) => Object.values(g));
    expect(all.length).toBeGreaterThan(30);
    for (const i of all) {
      expect(i.url).toMatch(/^https:\/\/(images\.unsplash\.com|images\.pexels\.com)\//);
      expect(i.alt.length).toBeGreaterThan(5);
      expect(["Unsplash", "Pexels", "Pixabay"]).toContain(i.source);
    }
  });
});

describe("DataTable", () => {
  const rows = [{ id: "1", name: "Revenue" }, { id: "2", name: "Orders" }];
  it("renders rows without a sort prop (regression: no crash when sortKey is undefined)", () => {
    render(<DataTable rows={rows} rowKey={(r) => r.id} columns={[{ key: "n", header: "Name", cell: (r) => r.name }]} />);
    expect(screen.getByText("Revenue")).toBeInTheDocument();
  });
  it("supports sorting and keyboard row activation", async () => {
    const onSort = vi.fn();
    const onRow = vi.fn();
    render(<DataTable rows={rows} rowKey={(r) => r.id} sort="name" onSort={onSort} onRowClick={onRow} columns={[{ key: "n", header: "Name", sortKey: "name", cell: (r) => r.name }]} />);
    expect(screen.getByRole("columnheader")).toHaveAttribute("aria-sort", "ascending");
    await userEvent.click(screen.getByRole("button", { name: /Name/ }));
    expect(onSort).toHaveBeenCalledWith("-name");
    const row = screen.getByText("Orders").closest("tr")!;
    fireEvent.keyDown(row, { key: "Enter" });
    expect(onRow).toHaveBeenCalledWith(rows[1]);
  });
  it("shows the empty state", () => {
    render(<DataTable rows={[]} rowKey={(r: any) => r.id} columns={[]} empty={<EmptyState title="Nothing here" />} />);
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
  });
});

describe("Pager", () => {
  it("pages forward and disables at the edges", async () => {
    const onPage = vi.fn();
    render(<Pager page={1} pageSize={10} total={35} onPage={onPage} />);
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPage).toHaveBeenCalledWith(2);
    expect(screen.getByText("1–10 of 35")).toBeInTheDocument();
  });
  it("renders nothing for a single page", () => {
    const { container } = render(<Pager page={1} pageSize={10} total={5} onPage={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("FormulaDiff", () => {
  it("highlights removed tokens on side A and added tokens on side B", () => {
    const segs = [{ op: "equal", a: "SUM(net_sales)", b: "SUM(net_sales)" }, { op: "insert", a: "", b: " - SUM(refund_amount)" }];
    const { container: a } = render(<FormulaDiff segments={segs} side="a" />);
    expect(a.querySelectorAll("mark")).toHaveLength(0);
    const { container: b } = render(<FormulaDiff segments={segs} side="b" />);
    expect(b.querySelector("mark")?.textContent).toContain("refund_amount");
  });
});

describe("ValidationPanel", () => {
  it("shows errors and success summaries", () => {
    const { rerender } = render(<ValidationPanel report={{ ok: false, errors: [{ message: "Unknown column 'x'" }], warnings: [] }} />);
    expect(screen.getByTestId("validation-panel")).toHaveAttribute("data-ok", "false");
    expect(screen.getByText("Unknown column 'x'")).toBeInTheDocument();
    rerender(<ValidationPanel report={{ ok: true, errors: [], warnings: ["careful"], columns: ["net_sales"], aggregations: ["SUM"], metrics: [], result_type: "numeric" }} />);
    expect(screen.getByText("Formula is valid")).toBeInTheDocument();
    expect(screen.getByText("careful")).toBeInTheDocument();
  });
});

describe("StatusBadge", () => {
  it("humanises status text", () => {
    render(<StatusBadge status="in_review" />);
    expect(screen.getByText("in review")).toBeInTheDocument();
  });
});

describe("RequireCap (frontend RBAC gate)", () => {
  const tree = (cap: string) => (
    <MemoryRouter initialEntries={["/secret"]}>
      <Routes>
        <Route path="/secret" element={<RequireCap cap={cap}><p>secret page</p></RequireCap>} />
        <Route path="/403" element={<p>forbidden</p>} />
      </Routes>
    </MemoryRouter>
  );
  it("renders children when the capability is held", () => { render(tree("chat.ask")); expect(screen.getByText("secret page")).toBeInTheDocument(); });
  it("redirects to /403 otherwise", () => { render(tree("user.manage")); expect(screen.getByText("forbidden")).toBeInTheDocument(); });
});

describe("formatters", () => {
  it("formats values by unit", () => {
    expect(formatValue(1245300, "INR")).toBe("₹12,45,300");
    expect(formatValue(1234567.891, "INR")).toBe("₹12,34,568");
    expect(formatValue(45.5, "INR")).toBe("₹45.50");
    expect(formatValue(-250000, "INR")).toBe("-₹2,50,000");
    expect(formatValue(35.04, "percent")).toBe("35%");
    expect(formatValue(1603, "count")).toBe("1,603");
    expect(formatValue(12345678, "count")).toBe("1,23,45,678");
    expect(formatValue(null)).toBe("—");
    expect(formatBytes(1536)).toBe("1.5 KB");
  });
  it("compacts amounts into lakh / crore for KPI cards and chart axes", () => {
    expect(compactIN(12000000, true)).toBe("₹1.2 Cr");
    expect(compactIN(4500000, true)).toBe("₹45 L");
    expect(compactIN(12500)).toBe("12.5 K");
    expect(compact(1500000)).toBe("15 L");
    expect(axisFormat("INR")(25000000)).toBe("₹2.5 Cr");
    expect(axisFormat("count")(25000000)).toBe("2.5 Cr");
  });
  it("shows dates as DD-MMM-YYYY in IST", () => {
    expect(fmtDay("2026-03-05")).toBe("05-Mar-2026");
    expect(fmtDate("2025-12-31T20:00:00Z")).toBe("01-Jan-2026"); // 01:30 IST next day
    expect(fmtDateTime("2025-12-31T20:00:00Z")).toBe("01-Jan-2026 01:30 IST");
    expect(fmtDate("2026-10-24 06:30:00")).toBe("24-Oct-2026"); // naive API timestamps are UTC
  });
  it("escapes CSV", () => {
    expect(toCsv(["a", "b"], [["x,y", 'he said "hi"']])).toBe('a,b\n"x,y","he said ""hi"""');
  });
});
