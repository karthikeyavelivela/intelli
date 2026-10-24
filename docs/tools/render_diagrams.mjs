// Renders every docs/diagrams/src/*.mmd (Mermaid) to SVG and PNG in docs/diagrams using headless Chromium.
// Usage: node docs/tools/render_diagrams.mjs
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "../../frontend/node_modules/@playwright/test/index.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, "..", "diagrams", "src");
const out = path.join(here, "..", "diagrams");
const mermaidJs = pathToFileURL(path.join(here, "node_modules", "mermaid", "dist", "mermaid.min.js")).href;

const browser = await chromium.launch();
const ctx = await browser.newContext({ deviceScaleFactor: 2, viewport: { width: 1600, height: 1000 } });
const page = await ctx.newPage();
const hostFile = path.join(here, "_host.html");
fs.writeFileSync(hostFile, `<!doctype html><html><head><meta charset="utf-8"></head><body style="margin:0;background:#fff"><div id="host" style="display:inline-block;padding:24px;background:#fff"></div><script charset="utf-8" src="${mermaidJs}"></script></body></html>`);
await page.goto(pathToFileURL(hostFile).href);
await page.waitForFunction(() => typeof window.mermaid !== "undefined");
await page.evaluate(() => window.mermaid.initialize({ startOnLoad: false, theme: "neutral", securityLevel: "loose", flowchart: { htmlLabels: true, curve: "basis", useMaxWidth: false }, sequence: { useMaxWidth: false }, er: { useMaxWidth: false }, state: { useMaxWidth: false }, fontFamily: "Arial, Helvetica, sans-serif" }));

let ok = 0;
for (const f of fs.readdirSync(src).filter((n) => n.endsWith(".mmd")).sort()) {
  const name = f.replace(/\.mmd$/, "");
  const code = fs.readFileSync(path.join(src, f), "utf8");
  try {
    const svg = await page.evaluate(async ([id, c]) => {
      const r = await window.mermaid.render(id, c);
      document.getElementById("host").innerHTML = r.svg;
      return r.svg;
    }, ["d_" + name.replace(/\W/g, "_"), code]);
    fs.writeFileSync(path.join(out, name + ".svg"), svg);
    const el = page.locator("#host");
    await el.screenshot({ path: path.join(out, name + ".png") });
    ok++;
    console.log("rendered", name);
  } catch (e) {
    console.error("FAILED", name, String(e).split("\n")[0]);
    process.exitCode = 1;
  }
}
fs.rmSync(hostFile, { force: true });
await browser.close();
console.log(`${ok} diagrams rendered to ${out}`);
