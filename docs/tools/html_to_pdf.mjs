// Usage: node docs/tools/html_to_pdf.mjs input.html output.pdf "footer text"
import path from "node:path";
import { pathToFileURL } from "node:url";
import { chromium } from "../../frontend/node_modules/@playwright/test/index.mjs";

const [, , input, output, footer = ""] = process.argv;
const browser = await chromium.launch();
const page = await browser.newPage();
await page.goto(pathToFileURL(path.resolve(input)).href, { waitUntil: "load" });
await page.pdf({
  path: path.resolve(output),
  format: "A4",
  printBackground: true,
  displayHeaderFooter: true,
  margin: { top: "18mm", bottom: "20mm", left: "16mm", right: "16mm" },
  headerTemplate: "<span></span>",
  footerTemplate: `<div style="font-size:8px;color:#666;width:100%;text-align:center;font-family:Arial">${footer.replace(/</g, "&lt;")} &nbsp;|&nbsp; Page <span class="pageNumber"></span> of <span class="totalPages"></span></div>`,
});
await browser.close();
