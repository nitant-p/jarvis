import { expect, test } from "@playwright/test";
import { DateTime } from "luxon";

test("review, create, edit, and delete an event on desktop and phone", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") errors.push(message.text());
  });
  page.on("pageerror", (error) => errors.push(error.message));
  await page.goto("/");
  await page
    .getByLabel("Workspace access token")
    .fill("e2e-private-workspace-token");
  await page.getByRole("button", { name: "Open my workspace" }).click();
  await expect(
    page.getByRole("heading", { name: "Make space for what matters." }),
  ).toBeVisible();
  await page.getByRole("button", { name: "+ Add event", exact: true }).click();
  const dialog = page.getByRole("dialog");
  const title = `Dinner ${Date.now()}`;
  await dialog.getByLabel("Title", { exact: true }).fill(title);
  // Choose a visible day in the current week, avoiding reliance on the host's timezone.
  const start = DateTime.now().setZone("Asia/Singapore").toISODate() + "T19:00";
  await dialog.getByLabel("Starts", { exact: false }).fill(start);
  await dialog.getByLabel("Location").fill("Home");
  await dialog.getByRole("button", { name: "Preview change" }).click();
  const proposal = page
    .locator("article.proposal")
    .filter({ hasText: title })
    .first();
  await expect(proposal).toContainText("pending");
  // A proposal must not appear as a real event until accepted.
  await expect(
    page.locator(".fc-event-title").filter({ hasText: title }),
  ).toHaveCount(0);
  if (await proposal.getByLabel("Allow this overlap").count())
    await proposal.getByLabel("Allow this overlap").check();
  await proposal.getByRole("button", { name: "Accept change" }).click();
  await expect(
    page.locator(".fc-event-title").filter({ hasText: title }),
  ).toBeVisible({ timeout: 15000 });
  await page.locator(".fc-event-title").filter({ hasText: title }).click();
  await dialog.getByLabel("Title", { exact: true }).fill(title + " edited");
  await dialog.getByRole("button", { name: "Preview change" }).click();
  const update = page
    .locator("article.proposal")
    .filter({ hasText: title + " edited" })
    .first();
  if (await update.getByLabel("Allow this overlap").count())
    await update.getByLabel("Allow this overlap").check();
  await update.getByRole("button", { name: "Accept change" }).click();
  await expect(
    page.locator(".fc-event-title").filter({ hasText: title + " edited" }),
  ).toBeVisible({ timeout: 15000 });
  await page
    .locator(".fc-event-title")
    .filter({ hasText: title + " edited" })
    .click();
  await dialog.getByRole("button", { name: "Propose deletion" }).click();
  const deletion = page
    .locator("article.proposal")
    .filter({ hasText: title + " edited" })
    .filter({ hasText: "event delete" })
    .first();
  await deletion.getByRole("button", { name: "Accept change" }).click();
  await expect(
    page.locator(".fc-event-title").filter({ hasText: title }),
  ).toHaveCount(0, { timeout: 15000 });
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({
    path: `test-results/workspace-${test.info().project.name}.png`,
    fullPage: true,
  });
  expect(errors).toEqual([]);
});
