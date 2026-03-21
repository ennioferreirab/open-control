import { expect, test } from "@playwright/test";
import * as path from "path";
import * as fs from "fs";
import * as os from "os";

/**
 * E2E test: Launch a squad mission with file attachments.
 *
 * Prerequisites (real running stack):
 *   - `make start` or `make takeover` running
 *   - At least one published squad with a workflow bound to the active board
 *
 * The test creates a temporary fixture file, navigates through the real UI to
 * attach it in the Run Squad Mission dialog, launches, and verifies the file
 * metadata appears in the created task's Files tab.
 */

test.describe("Squad mission with file attachments", () => {
  let fixtureDir: string;
  let fixturePath: string;

  test.beforeAll(() => {
    fixtureDir = fs.mkdtempSync(path.join(os.tmpdir(), "e2e-mission-files-"));
    fixturePath = path.join(fixtureDir, "test-brief.txt");
    fs.writeFileSync(fixturePath, "This is a test brief for the squad mission.\n".repeat(10));
  });

  test.afterAll(() => {
    fs.rmSync(fixtureDir, { recursive: true, force: true });
  });

  test("attaches a file to a squad mission and verifies it on the task", async ({ page }) => {
    // ── 1. Navigate to dashboard ──────────────────────────────────────
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Mission Control/i })).toBeVisible();

    // ── 2. Find a squad in the sidebar and click it ───────────────────
    // The sidebar shows squads under the "Squads" label. Pick the first one.
    const squadsLabel = page.getByText("Squads", { exact: true });
    await expect(squadsLabel).toBeVisible({ timeout: 10_000 });

    // Squad items are SidebarMenuButtons with a violet circle (initials).
    // Click the first squad button after the "Squads" label.
    const squadButtons = page.locator('[data-sidebar="menu-button"]').filter({
      has: page.locator(".bg-violet-500"),
    });
    const squadCount = await squadButtons.count();
    test.skip(squadCount === 0, "No published squads found — skipping");

    await squadButtons.first().click();

    // ── 3. Wait for SquadDetailSheet to open ──────────────────────────
    const sheet = page.getByRole("dialog");
    await expect(sheet).toBeVisible({ timeout: 5_000 });

    // ── 4. Click "Run Mission" ────────────────────────────────────────
    const runMissionBtn = sheet.getByRole("button", { name: /Run Mission/i });
    // Skip if the squad isn't published or no workflow is bound
    const runMissionVisible = await runMissionBtn.isVisible().catch(() => false);
    test.skip(
      !runMissionVisible,
      "Run Mission button not visible — squad not published or no workflow bound",
    );

    await runMissionBtn.click();

    // ── 5. Fill in the Run Squad Mission dialog ───────────────────────
    const missionDialog = page.getByRole("dialog").filter({
      has: page.getByText("Run Squad Mission"),
    });
    await expect(missionDialog).toBeVisible({ timeout: 3_000 });

    const missionTitle = `E2E file attach ${Date.now()}`;
    await missionDialog.getByPlaceholder(/review q4 release plan/i).fill(missionTitle);
    await missionDialog
      .getByPlaceholder(/provide context/i)
      .fill("Automated e2e test with file attachment");

    // ── 6. Attach a file via the hidden input ─────────────────────────
    const fileInput = missionDialog.locator('input[type="file"]');
    await fileInput.setInputFiles(fixturePath);

    // Verify the file chip appeared
    await expect(missionDialog.getByText("test-brief.txt")).toBeVisible();

    // ── 7. Launch ─────────────────────────────────────────────────────
    const launchBtn = missionDialog.getByRole("button", { name: /Launch Mission/i });
    await expect(launchBtn).toBeEnabled();
    await launchBtn.click();

    // Dialog should close after successful launch
    await expect(missionDialog).not.toBeVisible({ timeout: 10_000 });

    // ── 8. Find the created task and open it ──────────────────────────
    // After launch, the SquadDetailSheet should still be open or we're
    // back on the kanban. Search for the task by title.
    // Close any remaining sheets first
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");

    const searchInput = page.getByLabel("Search tasks");
    await expect(searchInput).toBeVisible({ timeout: 5_000 });
    await searchInput.fill(missionTitle);

    // Expand the Untagged group if collapsed (same pattern as smoke test)
    const expandButton = page.getByRole("button", { name: /Expand Untagged/ });
    if (await expandButton.isVisible().catch(() => false)) {
      await expandButton.click();
    }

    const taskCard = page.getByRole("article", { name: new RegExp(missionTitle) }).first();
    await expect(taskCard).toBeVisible({ timeout: 10_000 });
    await taskCard.click();

    // ── 9. Verify the Files tab shows the attached file ───────────────
    const filesTab = page.getByRole("tab", { name: /Files/i });
    await expect(filesTab).toBeVisible({ timeout: 5_000 });

    // The tab label shows "Files (1)" when a file is attached
    await expect(filesTab).toHaveText(/Files\s*\(1\)/, { timeout: 10_000 });

    await filesTab.click();
    await expect(page.getByText("test-brief.txt")).toBeVisible({ timeout: 5_000 });
  });
});
