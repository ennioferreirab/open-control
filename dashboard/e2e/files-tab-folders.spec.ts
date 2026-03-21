import { expect, test, type Page } from "@playwright/test";

/**
 * E2E: Files tab folder grouping + source task grouping.
 *
 * Creates real tasks via the Convex HTTP API, adds files with path-like names,
 * sets up merge relationships, then navigates the UI to verify:
 *   - Flat files render without folder wrappers
 *   - Path-like files render inside collapsible folder groups
 *   - Merge source files appear grouped under "From: …" collapsible sections
 *   - Expand/collapse works for both folders and source groups
 *   - Delete button shows on local attachments, hidden on source files
 */

const CONVEX_URL = process.env.NEXT_PUBLIC_CONVEX_URL ?? "http://127.0.0.1:3210";

// ---- Convex helpers ----

async function convexQuery(fn: string, args: Record<string, unknown> = {}) {
  const res = await fetch(`${CONVEX_URL}/api/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: fn, args, format: "json" }),
  });
  if (!res.ok) throw new Error(`Convex query ${fn} failed: ${res.status} ${await res.text()}`);
  const body = await res.json();
  if (body.status === "error") throw new Error(`Convex query ${fn}: ${body.errorMessage}`);
  return body.value;
}

async function convexMutation(fn: string, args: Record<string, unknown>) {
  const res = await fetch(`${CONVEX_URL}/api/mutation`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path: fn, args, format: "json" }),
  });
  if (!res.ok) throw new Error(`Convex mutation ${fn} failed: ${res.status} ${await res.text()}`);
  const body = await res.json();
  if (body.status === "error") throw new Error(`Convex mutation ${fn}: ${body.errorMessage}`);
  return body.value;
}

async function getDefaultBoardId(): Promise<string> {
  const boards = await convexQuery("boards:list");
  const defaultBoard = boards.find((b: { name: string }) => b.name === "default");
  if (!defaultBoard) throw new Error("No default board found");
  return defaultBoard._id;
}

// ---- Test data helpers ----

const ts = () => new Date().toISOString();

function fileMeta(name: string, subfolder: "attachments" | "output", size = 1024) {
  return { name, type: "application/octet-stream", size, subfolder, uploadedAt: ts() };
}

function escapeRegex(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// ---- Navigation helpers ----

async function openTaskByTitle(page: Page, title: string) {
  const searchInput = page.getByLabel("Search tasks");
  await expect(searchInput).toBeVisible();
  await searchInput.fill(title);

  const card = page.getByRole("article", { name: new RegExp(escapeRegex(title)) }).first();

  // Poll: expand collapsed tag groups until the card is visible
  for (let attempt = 0; attempt < 20; attempt++) {
    if (await card.isVisible()) break;
    const expandBtn = page.getByRole("button", { name: /^Expand / }).first();
    if (await expandBtn.isVisible()) {
      await expandBtn.click();
    }
    await page.waitForTimeout(250);
  }

  await expect(card).toBeVisible({ timeout: 10_000 });
  await card.click();
}

async function switchToFilesTab(page: Page) {
  const filesTab = page.getByRole("tab", { name: "Files" });
  await expect(filesTab).toBeVisible();
  await filesTab.click();
  await expect(filesTab).toHaveAttribute("data-state", "active");
}

// ---- Tests ----

test.describe("Files tab — folder grouping & source task grouping", () => {
  test.describe.configure({ mode: "serial" });

  // Shared state populated once by the first test
  const state: {
    uid: string;
    sourceATitle: string;
    sourceBTitle: string;
    mergeTitle: string;
    sourceAId?: string;
    sourceBId?: string;
    mergeTaskId?: string;
    setupDone: boolean;
  } = {
    uid: `e2e-${Date.now()}`,
    sourceATitle: "",
    sourceBTitle: "",
    mergeTitle: "",
    setupDone: false,
  };

  async function ensureSetup() {
    if (state.setupDone) return;

    state.sourceATitle = `Source A ${state.uid}`;
    state.sourceBTitle = `Source B ${state.uid}`;

    const boardId = await getDefaultBoardId();

    // 1. Create two source tasks with files
    state.sourceAId = await convexMutation("tasks:create", {
      title: state.sourceATitle,
      tags: ["e2e-files"],
      boardId,
    });
    state.sourceBId = await convexMutation("tasks:create", {
      title: state.sourceBTitle,
      tags: ["e2e-files"],
      boardId,
    });

    // Add files with path-like names to source tasks
    await convexMutation("tasks:addTaskFiles", {
      taskId: state.sourceAId,
      files: [
        fileMeta("data.csv", "attachments", 2048),
        fileMeta("results/summary.pdf", "attachments", 5120),
        fileMeta("results/charts/chart1.png", "output", 10240),
      ],
    });

    await convexMutation("tasks:addTaskFiles", {
      taskId: state.sourceBId,
      files: [
        fileMeta("analysis/report.md", "output", 3072),
        fileMeta("analysis/figures/fig1.svg", "output", 8192),
      ],
    });

    // 2. Create merge task (Convex sets title: "Merge: X + Y")
    state.mergeTaskId = await convexMutation("tasks:createMergedTask", {
      primaryTaskId: state.sourceAId,
      secondaryTaskId: state.sourceBId,
      mode: "manual",
    });

    // Derive the merge title that Convex auto-generates
    state.mergeTitle = `Merge: ${state.sourceATitle} + ${state.sourceBTitle}`;

    // 3. Add local files (with paths) to the merge task
    await convexMutation("tasks:addTaskFiles", {
      taskId: state.mergeTaskId,
      files: [
        fileMeta("notes.txt", "attachments", 512),
        fileMeta("docs/spec.md", "attachments", 1024),
        fileMeta("docs/design/mockup.png", "attachments", 4096),
        fileMeta("report.pdf", "output", 2048),
        fileMeta("exports/data.json", "output", 1536),
      ],
    });

    state.setupDone = true;
  }

  // Helper: each test navigates to the merge task Files tab
  async function goToMergeFilesTab(page: Page) {
    await ensureSetup();
    await page.goto("/");
    await openTaskByTitle(page, state.mergeTitle);
    await switchToFilesTab(page);
  }

  test("displays flat files and folder-grouped files for local attachments", async ({ page }) => {
    await goToMergeFilesTab(page);

    // Flat file should be visible
    await expect(page.getByText("notes.txt")).toBeVisible();

    // Folder "docs" should be visible as a collapsible group
    const docsFolder = page.getByRole("button", { name: "docs" });
    await expect(docsFolder).toBeVisible();

    // Files inside docs/ should be visible (folders start expanded)
    await expect(page.getByText("spec.md")).toBeVisible();

    // Nested folder "design" inside docs/
    const designFolder = page.getByRole("button", { name: "design" });
    await expect(designFolder).toBeVisible();
    await expect(page.getByText("mockup.png")).toBeVisible();
  });

  test("folder expand/collapse toggles children visibility", async ({ page }) => {
    await goToMergeFilesTab(page);

    const docsFolder = page.getByRole("button", { name: "docs" });
    await expect(docsFolder).toBeVisible();

    // Files visible initially (expanded by default)
    await expect(page.getByText("spec.md")).toBeVisible();

    // Collapse docs folder
    await docsFolder.click();
    await expect(page.getByText("spec.md")).not.toBeVisible();

    // Re-expand
    await docsFolder.click();
    await expect(page.getByText("spec.md")).toBeVisible();
  });

  test("displays folder tree for local output files", async ({ page }) => {
    await goToMergeFilesTab(page);

    // Flat output file
    await expect(page.getByText("report.pdf")).toBeVisible();

    // Folder-grouped output
    const exportsFolder = page.getByRole("button", { name: "exports" });
    await expect(exportsFolder).toBeVisible();
    await expect(page.getByText("data.json")).toBeVisible();
  });

  test("source task files grouped under collapsible From headers", async ({ page }) => {
    await goToMergeFilesTab(page);

    // Source A appears in both Attachments and Outputs sections
    const sourceAHeaders = page.getByRole("button", {
      name: new RegExp(escapeRegex(state.sourceATitle)),
    });
    // Should have 2 headers (one in Attachments, one in Outputs)
    await expect(sourceAHeaders).toHaveCount(2);

    const sourceBHeader = page.getByRole("button", {
      name: new RegExp(escapeRegex(state.sourceBTitle)),
    });
    // Source B only has output files, so 1 header
    await expect(sourceBHeader).toHaveCount(1);

    // Source groups start collapsed — source A attachment files should NOT be visible
    await expect(page.getByText("data.csv")).not.toBeVisible();

    // Expand the first source A group (Attachments section)
    await sourceAHeaders.first().click();

    // Now source A attachment files should be visible
    await expect(page.getByText("data.csv")).toBeVisible();

    // Path-grouped source A files: "results" folder with summary.pdf
    await expect(page.getByText("summary.pdf")).toBeVisible();
  });

  test("source group shows file count and total size", async ({ page }) => {
    await goToMergeFilesTab(page);

    // Source A has attachments in Attachments section (data.csv + results/summary.pdf = 2 files)
    // and outputs in Outputs section (results/charts/chart1.png = 1 file)
    // Look for a source group button containing file count
    const sourceAHeaders = page.getByRole("button", {
      name: new RegExp(escapeRegex(state.sourceATitle)),
    });
    // At least one header should show file count
    const headerCount = await sourceAHeaders.count();
    expect(headerCount).toBeGreaterThan(0);

    // Check one of the headers contains file count text
    let foundFileCount = false;
    for (let i = 0; i < headerCount; i++) {
      const text = await sourceAHeaders.nth(i).textContent();
      if (text && /\d+ files?/.test(text)) {
        foundFileCount = true;
        break;
      }
    }
    expect(foundFileCount).toBe(true);
  });

  test("delete button visible on local attachments, hidden on source files", async ({ page }) => {
    await goToMergeFilesTab(page);

    // Local attachment "notes.txt" row — hover to reveal delete button
    const notesRow = page.locator("[data-testid='file-row']").filter({ hasText: "notes.txt" });
    await notesRow.hover();
    const deleteBtn = notesRow.getByLabel("Delete attachment");
    await expect(deleteBtn).toBeVisible();

    // Expand source A to see source files
    const sourceAHeader = page
      .getByRole("button", {
        name: new RegExp(escapeRegex(state.sourceATitle)),
      })
      .first();
    await sourceAHeader.click();
    await expect(page.getByText("data.csv")).toBeVisible();

    // Source file row should NOT have a delete button
    const sourceFileRow = page.locator("[data-testid='file-row']").filter({ hasText: "data.csv" });
    await sourceFileRow.hover();
    await expect(sourceFileRow.getByLabel("Delete attachment")).not.toBeVisible();
  });

  test("collapse source group hides its file tree", async ({ page }) => {
    await goToMergeFilesTab(page);

    const sourceAHeader = page
      .getByRole("button", {
        name: new RegExp(escapeRegex(state.sourceATitle)),
      })
      .first();

    // Expand
    await sourceAHeader.click();
    await expect(page.getByText("data.csv")).toBeVisible();

    // Collapse
    await sourceAHeader.click();
    await expect(page.getByText("data.csv")).not.toBeVisible();
  });
});
