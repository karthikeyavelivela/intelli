import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, ApiError, qs, setAuthLostHandler, streamAsk } from "@/lib/api";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });

describe("api client", () => {
  const fetchMock = vi.fn();
  beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal("fetch", fetchMock); });
  afterEach(() => vi.unstubAllGlobals());

  it("sends cookies and the CSRF header on every call, JSON-encoding bodies", async () => {
    fetchMock.mockResolvedValueOnce(json({ ok: true }));
    await api.post("/metrics", { name: "Revenue" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/metrics");
    expect(init.credentials).toBe("include");
    expect(init.headers["X-Requested-With"]).toBe("IntelliMetrics");
    expect(init.headers["Content-Type"]).toBe("application/json");
    expect(init.body).toBe('{"name":"Revenue"}');
  });

  it("turns the backend error envelope into an ApiError with code, details and request id", async () => {
    fetchMock.mockResolvedValueOnce(json({ error: { code: "invalid_formula", message: "Unknown column 'x'", details: [{ position: 4 }], request_id: "abc123" } }, 422));
    await expect(api.get("/x")).rejects.toMatchObject({ status: 422, code: "invalid_formula", message: "Unknown column 'x'", requestId: "abc123", details: [{ position: 4 }] });
    fetchMock.mockResolvedValueOnce(new Response("boom", { status: 500, statusText: "Server Error" }));
    const err = await api.get("/y").catch((e) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(500);
  });

  it("refreshes the session once on 401 and retries the original request", async () => {
    fetchMock
      .mockResolvedValueOnce(json({ error: { code: "token_expired", message: "Session expired" } }, 401))
      .mockResolvedValueOnce(json({ user: {} }))
      .mockResolvedValueOnce(json({ items: [1] }));
    const res = await api.get("/metrics");
    expect(res).toEqual({ items: [1] });
    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual(["/api/metrics", "/api/auth/refresh", "/api/metrics"]);
  });

  it("signs the user out when the refresh fails", async () => {
    const lost = vi.fn();
    setAuthLostHandler(lost);
    fetchMock.mockResolvedValueOnce(json({ error: { code: "unauthorized", message: "no" } }, 401)).mockResolvedValueOnce(json({}, 401));
    await expect(api.get("/datasets")).rejects.toMatchObject({ status: 401 });
    expect(lost).toHaveBeenCalled();
  });

  it("never retries auth endpoints (login failures surface directly)", async () => {
    fetchMock.mockResolvedValueOnce(json({ error: { code: "invalid_credentials", message: "Invalid email or password" } }, 401));
    await expect(api.post("/auth/login", {})).rejects.toMatchObject({ code: "invalid_credentials" });
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("builds query strings without empty values", () => {
    expect(qs({ q: "net sales", status: "", page: 2, x: undefined })).toBe("?q=net+sales&page=2");
    expect(qs({})).toBe("");
  });

  it("parses the Ask TARA server-sent-event stream", async () => {
    const enc = new TextEncoder();
    const body = new ReadableStream({
      start(c) {
        c.enqueue(enc.encode('event: status\ndata: {"conversation_id":"c1"}\n\nevent: text\ndata: {"delta":"Hel"}\n\n'));
        c.enqueue(enc.encode('event: text\ndata: {"delta":"lo"}\n\nevent: done\ndata: {"text":"Hello"}\n\n'));
        c.close();
      },
    });
    fetchMock.mockResolvedValueOnce(new Response(body, { status: 200 }));
    const events: [string, any][] = [];
    await streamAsk("hi", null, (e, d) => events.push([e, d]));
    expect(events.map((e) => e[0])).toEqual(["status", "text", "text", "done"]);
    expect(events.filter((e) => e[0] === "text").map((e) => e[1].delta).join("")).toBe("Hello");
  });
});
