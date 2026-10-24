import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { PublicLayout } from "@/layouts/PublicLayout";
import { ThemeProvider } from "@/lib/theme";
import Landing from "@/pages/public/Landing";

vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: null, can: () => false }) }));

function page() {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={["/"]}>
        <Routes><Route element={<PublicLayout />}><Route index element={<Landing />} /></Route></Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe("public landing page (academic project)", () => {
  it("contains no pricing, plans, billing or sales calls to action", () => {
    page();
    const text = document.body.textContent || "";
    for (const banned of [/pricing/i, /per month/i, /\/mo\b/i, /free trial/i, /start free/i, /upgrade/i, /contact sales/i, /billing/i, /subscription/i, /\btiers?\b/i]) {
      expect(text).not.toMatch(banned);
    }
    expect(screen.queryByRole("link", { name: /pricing/i })).toBeNull();
  });

  it("shows academic calls to action and the University Project badge + footer note", () => {
    page();
    expect(screen.getAllByRole("link", { name: /get started/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /explore the demo/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: /about this project/i }).length).toBeGreaterThan(0);
    expect(screen.getByTestId("university-badge")).toHaveTextContent(/university project/i);
    expect(screen.getByTestId("university-note")).toHaveTextContent(/synthetic demonstration data/i);
  });

  it("uses Indian rupee for illustrative figures", () => {
    page();
    expect(document.body.textContent).toContain("₹");
    expect(document.body.textContent).not.toMatch(/\$\d/);
  });
});
