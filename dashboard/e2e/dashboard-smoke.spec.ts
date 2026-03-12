import { expect, test } from "@playwright/test";

test("dashboard shell journey stays functional", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: /Mission Control/i })).toBeVisible();

  const taskTitle = `Playwright smoke ${Date.now()}`;
  await page.getByPlaceholder("Task title...").fill(taskTitle);
  await page.getByRole("button", { name: "Create", exact: true }).click();

  const searchInput = page.getByLabel("Search tasks");
  await expect(searchInput).toBeVisible();
  await searchInput.fill(taskTitle);
  await expect(searchInput).toHaveValue(taskTitle);

  const collapsedGroup = page.getByRole("button", { name: /Expand Untagged/ });
  await expect(collapsedGroup).toBeVisible();
  await collapsedGroup.click();

  const createdTask = page.getByRole("article", { name: new RegExp(taskTitle) }).first();
  await expect(createdTask).toBeVisible();
  await createdTask.click();

  const threadTab = page.getByRole("tab", { name: "Thread" });
  const planTab = page.getByRole("tab", { name: "Execution Plan" });
  await expect(threadTab).toBeVisible();
  await expect(planTab).toBeVisible();
  await planTab.click();
  await expect(planTab).toHaveAttribute("data-state", "active");
  await threadTab.click();
  await expect(threadTab).toHaveAttribute("data-state", "active");
  await page.keyboard.press("Escape");

  await searchInput.clear();
  await expect(searchInput).toHaveValue("");

  await page.getByLabel("Open settings").click();
  await expect(page.getByRole("heading", { name: "Settings" }).last()).toBeVisible();
  await page.keyboard.press("Escape");

  await page.getByLabel("Show activity feed").click();
  await expect(page.getByRole("heading", { name: "Activity Feed" })).toBeVisible();
  await page.getByRole("tab", { name: "Activity" }).click();
  await expect(page.getByRole("tab", { name: "Activity" })).toHaveAttribute("data-state", "active");
});
