import { expect, type Locator, type Page } from "@playwright/test";

export const USERS = {
  admin: ["admin@intellimetrics.demo", "Admin@12345"],
  analyst: ["analyst@intellimetrics.demo", "Analyst@12345"],
  business: ["business@intellimetrics.demo", "Business@12345"],
  reviewer: ["reviewer@intellimetrics.demo", "Reviewer@12345"],
} as const;

export async function login(page: Page, who: keyof typeof USERS) {
  await page.goto("/login");
  await page.getByTestId("login-email").fill(USERS[who][0]);
  await page.getByTestId("login-password").fill(USERS[who][1]);
  await page.getByTestId("login-submit").click();
  await expect(page).toHaveURL(/\/app\/dashboard/);
}

/** Select an <option> whose visible text contains `text` (waits for options that load asynchronously). */
export async function pick(select: Locator, text: string) {
  const find = async () => (await select.locator("option").allTextContents()).findIndex((o) => o.includes(text));
  await expect.poll(find, { message: `option containing "${text}"`, timeout: 15_000 }).toBeGreaterThanOrEqual(0);
  await select.selectOption({ index: await find() });
}
