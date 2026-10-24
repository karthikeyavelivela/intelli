// Verifies that every URL in src/config/images.ts returns HTTP 200 with an image content type.
// Usage: node e2e/verify-images.mjs [--json out.json]
import fs from "node:fs";

const src = fs.readFileSync(new URL("../src/config/images.ts", import.meta.url), "utf8");
const U = (id, w = 1600, q = 80) => `https://images.unsplash.com/${id}?w=${w}&q=${q}&auto=format&fit=crop`;
const P = (id, w = 1600) => `https://images.pexels.com/photos/${id}/pexels-photo-${id}.jpeg?auto=compress&cs=tinysrgb&w=${w}`;
const urls = new Set();
for (const m of src.matchAll(/\bU\("([^"]+)"(?:,\s*(\d+))?(?:,\s*(\d+))?\)/g)) urls.add(U(m[1], m[2] ? +m[2] : 1600, m[3] ? +m[3] : 80));
for (const m of src.matchAll(/\bP\((\d+)(?:,\s*(\d+))?\)/g)) urls.add(P(+m[1], m[2] ? +m[2] : 1600));
const results = [];
for (const url of urls) {
  try {
    const r = await fetch(url, { method: "GET", redirect: "follow" });
    results.push({ url, status: r.status, type: r.headers.get("content-type"), ok: r.status === 200 && (r.headers.get("content-type") || "").startsWith("image/") });
    await r.body?.cancel();
  } catch (e) {
    results.push({ url, status: 0, type: String(e), ok: false });
  }
}
const bad = results.filter((r) => !r.ok);
console.log(`${results.length - bad.length}/${results.length} image URLs OK`);
bad.forEach((b) => console.log("FAIL", b.status, b.url));
const j = process.argv.indexOf("--json");
if (j > 0) fs.writeFileSync(process.argv[j + 1], JSON.stringify(results, null, 1));
process.exit(bad.length ? 1 : 0);
