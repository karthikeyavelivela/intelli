export class ApiError extends Error {
  status: number;
  code: string;
  details: any;
  requestId?: string;
  constructor(status: number, code: string, message: string, details?: any, requestId?: string) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

const BASE = "/api";
let refreshing: Promise<boolean> | null = null;
let onAuthLost: (() => void) | null = null;
export const setAuthLostHandler = (fn: () => void) => (onAuthLost = fn);

async function doRefresh(): Promise<boolean> {
  try {
    const r = await fetch(`${BASE}/auth/refresh`, { method: "POST", credentials: "include", headers: { "X-Requested-With": "IntelliMetrics" } });
    return r.ok;
  } catch {
    return false;
  }
}

async function parse(res: Response) {
  if (res.status === 204) return null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return res.json();
  return res;
}

export async function request<T = any>(method: string, path: string, body?: unknown, opts: { raw?: boolean; retry?: boolean; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = { "X-Requested-With": "IntelliMetrics" };
  let payload: BodyInit | undefined;
  if (opts.form) payload = opts.form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${BASE}${path}`, { method, headers, body: payload, credentials: "include" });
  if (res.status === 401 && opts.retry !== false && !path.startsWith("/auth/")) {
    const current = refreshing || (refreshing = doRefresh().finally(() => { refreshing = null; }));
    refreshing = current;
    if (await current) return request<T>(method, path, body, { ...opts, retry: false });
    onAuthLost?.();
  }
  if (!res.ok) {
    let err: any = null;
    try {
      err = (await res.json()).error;
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, err?.code || "http_error", err?.message || res.statusText || "Request failed", err?.details, err?.request_id);
  }
  if (opts.raw) return res as unknown as T;
  return (await parse(res)) as T;
}

export const api = {
  get: <T = any>(p: string) => request<T>("GET", p),
  post: <T = any>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  put: <T = any>(p: string, b?: unknown) => request<T>("PUT", p, b ?? {}),
  patch: <T = any>(p: string, b?: unknown) => request<T>("PATCH", p, b ?? {}),
  del: <T = any>(p: string) => request<T>("DELETE", p),
  upload: <T = any>(p: string, form: FormData) => request<T>("POST", p, undefined, { form }),
  blob: async (p: string) => {
    const res = await request<Response>("GET", p, undefined, { raw: true });
    return { blob: await res.blob(), filename: /filename="([^"]+)"/.exec(res.headers.get("content-disposition") || "")?.[1] || "export" };
  },
};

export function qs(params: Record<string, unknown>): string {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  });
  const s = u.toString();
  return s ? `?${s}` : "";
}

/** Consume the Ask TARA server-sent-events stream. */
export async function streamAsk(
  question: string,
  conversationId: string | null,
  on: (event: string, data: any) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/chat/ask/stream`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-Requested-With": "IntelliMetrics" },
    body: JSON.stringify({ question, conversation_id: conversationId }),
  });
  if (res.status === 401) {
    if (await doRefresh()) return streamAsk(question, conversationId, on);
    onAuthLost?.();
  }
  if (!res.ok || !res.body) {
    let err: any = null;
    try {
      err = (await res.json()).error;
    } catch {
      /* ignore */
    }
    throw new ApiError(res.status, err?.code || "http_error", err?.message || "Request failed");
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let idx;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const ev = /event: (.*)/.exec(chunk)?.[1];
      const data = /data: (.*)/s.exec(chunk)?.[1];
      if (ev && data) on(ev, JSON.parse(data));
    }
  }
}
