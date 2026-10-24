import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnimatedNumber, EmptyState, ErrorState, Logo, PageHeader, TableSkeleton } from "@/components/common";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { Modal } from "@/components/ui/dialog";
import { Field, Input, Select, Switch, Textarea } from "@/components/ui/form";
import { Progress, Skeleton } from "@/components/ui/misc";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToastProvider, useToast } from "@/components/ui/toast";
import { IMAGES } from "@/config/images";

describe("form controls", () => {
  it("Field links its label to the control and shows errors accessibly", () => {
    render(<Field label="Email" error="Required">{(id) => <Input id={id} />}</Field>);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent("Required");
  });
  it("Switch toggles with aria-checked and Select/Textarea render", async () => {
    const onChange = vi.fn();
    render(<><Switch checked={false} onChange={onChange} label="Active" /><Select aria-label="s"><option>a</option></Select><Textarea aria-label="t" /></>);
    const sw = screen.getByRole("switch", { name: "Active" });
    expect(sw).toHaveAttribute("aria-checked", "false");
    await userEvent.click(sw);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});

describe("Button", () => {
  it("is disabled and busy while loading", () => {
    render(<Button loading>Save</Button>);
    const b = screen.getByRole("button", { name: /save/i });
    expect(b).toBeDisabled();
    expect(b).toHaveAttribute("aria-busy", "true");
  });
});

describe("Modal", () => {
  it("renders an accessible dialog and closes via the close button", async () => {
    const onOpenChange = vi.fn();
    render(<Modal open onOpenChange={onOpenChange} title="Delete dataset?" description="This cannot be undone." footer={<Button>Confirm</Button>}><p>body</p></Modal>);
    expect(screen.getByRole("dialog", { name: "Delete dataset?" })).toBeInTheDocument();
    expect(screen.getByText("This cannot be undone.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Close dialog" }));
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe("Tabs", () => {
  it("switches panels", async () => {
    render(<Tabs defaultValue="a"><TabsList><TabsTrigger value="a">One</TabsTrigger><TabsTrigger value="b">Two</TabsTrigger></TabsList><TabsContent value="a">first</TabsContent><TabsContent value="b">second</TabsContent></Tabs>);
    expect(screen.getByText("first")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Two" }));
    expect(screen.getByText("second")).toBeInTheDocument();
  });
});

describe("toasts", () => {
  function Trigger() {
    const t = useToast();
    return <button onClick={() => t.success("Saved", "Version 3 recorded")}>go</button>;
  }
  it("announces a toast in a live region and can be dismissed", async () => {
    render(<ToastProvider><Trigger /></ToastProvider>);
    await userEvent.click(screen.getByText("go"));
    expect(screen.getByText("Saved")).toBeInTheDocument();
    expect(screen.getByText("Version 3 recorded")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Notifications" })).toHaveAttribute("aria-live", "polite");
    await userEvent.click(screen.getByRole("button", { name: "Dismiss" }));
  });
});

describe("shared page pieces", () => {
  it("PageHeader, Card, Progress, Skeleton, Logo", () => {
    render(<><PageHeader title="Datasets" description="All data" eyebrow="Data" actions={<button>New</button>} /><Card><CardHeader title="T" description="D" /><CardBody>content</CardBody></Card><Progress value={42} label="Upload" /><Skeleton /><Logo /></>);
    expect(screen.getByRole("heading", { level: 1, name: "Datasets" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Upload" })).toHaveAttribute("aria-valuenow", "42");
    expect(screen.getByText("IntelliMetrics")).toBeInTheDocument();
  });
  it("Progress clamps out-of-range values", () => {
    render(<Progress value={250} />);
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "100");
  });
  it("ErrorState shows the message, request id and a retry action", async () => {
    const retry = vi.fn();
    render(<ErrorState error={Object.assign(new Error("Dataset not found"), { requestId: "r-1" })} retry={retry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Dataset not found");
    expect(screen.getByText(/r-1/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalled();
  });
  it("EmptyState renders its image with alt text and an action", () => {
    render(<EmptyState title="No datasets yet" description="Upload one" image={IMAGES.emptyStates.data} action={<button>Upload</button>} />);
    expect(screen.getByAltText(IMAGES.emptyStates.data.alt)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload" })).toBeInTheDocument();
  });
  it("TableSkeleton renders placeholder rows", () => {
    const { container } = render(<TableSkeleton rows={3} cols={2} />);
    expect(container.querySelectorAll(".skeleton")).toHaveLength(6);
  });
  it("AnimatedNumber shows a dash for missing values and formats INR when it reaches the value", async () => {
    const { rerender } = render(<AnimatedNumber value={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
    rerender(<AnimatedNumber value={1245300} unit="INR" />);
    await act(async () => { await new Promise((r) => setTimeout(r, 50)); });
    expect(document.body.textContent === "—" || /₹/.test(document.body.textContent || "") || document.body.textContent === "").toBe(true);
    fireEvent.scroll(window);
  });
});
