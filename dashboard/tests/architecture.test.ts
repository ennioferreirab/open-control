/**
 * Architecture guardrail tests for the dashboard.
 *
 * These tests scan source files for import patterns that violate
 * architectural rules. They prevent accidental coupling regressions
 * and document the intended module boundaries.
 *
 * Rules:
 * 1. Feature components (KanbanBoard, TaskDetailSheet) must use hooks
 *    instead of directly importing useQuery/useMutation from convex/react.
 * 2. Hook files must not import UI components (no upward deps).
 * 3. Feature view hooks must consume the aggregated read models instead
 *    of reassembling task/board state from many raw Convex queries.
 * 4. Component test files in components/ must mock hooks, not convex/react.
 */

import { describe, it, expect } from "vitest";
import * as fs from "fs";
import * as path from "path";

const DASHBOARD_ROOT = path.resolve(__dirname, "..");

function readFileIfExists(filePath: string): string | null {
  try {
    return fs.readFileSync(filePath, "utf-8");
  } catch {
    return null;
  }
}

function fileContainsDirectConvexImport(content: string): boolean {
  const importRegex =
    /import\s+\{[^}]*(useQuery|useMutation)[^}]*\}\s+from\s+["']convex\/react["']/;
  return importRegex.test(content);
}

function fileContains(pattern: RegExp, content: string): boolean {
  return pattern.test(content);
}

describe("Architecture: Hook files must not import UI components", () => {
  it("hooks/ directory files should not import from components/", () => {
    const hooksDir = path.join(DASHBOARD_ROOT, "hooks");
    if (!fs.existsSync(hooksDir)) {
      return;
    }

    const hookFiles = fs
      .readdirSync(hooksDir)
      .filter((f: string) => f.endsWith(".ts") || f.endsWith(".tsx"))
      .filter((f: string) => !f.includes(".test."));

    for (const hookFile of hookFiles) {
      const content = fs.readFileSync(
        path.join(hooksDir, hookFile),
        "utf-8",
      );
      // Allow imports from context providers (e.g. BoardContext) —
      // these are shared state hooks that happen to live in components/
      const lines = content.split("\n").filter(
        (line: string) =>
          /from\s+["']@?\.?\.?\/?components\//.test(line) &&
          !/Context["']/.test(line)
      );
      const componentImports = lines.length > 0 ? lines : null;
      expect(
        componentImports,
        `hooks/${hookFile} imports from components/ -- hooks must not depend on UI components`,
      ).toBeNull();
    }
  });
});

describe("Architecture: Feature components must use hooks, not direct Convex imports", () => {
  const featureComponents = [
    "KanbanBoard.tsx",
    "TaskDetailSheet.tsx",
    "TaskInput.tsx",
    "AgentConfigSheet.tsx",
    "TagsPanel.tsx",
    "SearchBar.tsx",
    "StepCard.tsx",
    "AgentSidebarItem.tsx",
  ];

  for (const componentName of featureComponents) {
    it(`${componentName} should not directly import useQuery/useMutation from convex/react`, () => {
      const filePath = path.join(DASHBOARD_ROOT, "components", componentName);
      const content = readFileIfExists(filePath);
      if (!content) return;
      expect(
        fileContainsDirectConvexImport(content),
        `${componentName} must use feature hooks/view-models instead of direct useQuery/useMutation`,
      ).toBe(false);
    });
  }
});

describe("Architecture: Feature view hooks must consume read models", () => {
  it("useTaskDetailView.ts should read from tasks.getDetailView", () => {
    const filePath = path.join(DASHBOARD_ROOT, "hooks", "useTaskDetailView.ts");
    const content = readFileIfExists(filePath);
    if (!content) return;

    expect(
      fileContains(/api\.tasks\.getDetailView/, content),
      "useTaskDetailView.ts must use api.tasks.getDetailView as its primary read path",
    ).toBe(true);
    expect(
      fileContains(/api\.tasks\.getById|api\.messages\.listByTask|api\.steps\.getByTask/, content),
      "useTaskDetailView.ts must not rebuild task detail state from raw task/message/step queries",
    ).toBe(false);
  });

  it("useBoardView.ts should read from boards.getBoardView", () => {
    const filePath = path.join(DASHBOARD_ROOT, "hooks", "useBoardView.ts");
    const content = readFileIfExists(filePath);
    if (!content) return;

    expect(
      fileContains(/api\.boards\.getBoardView/, content),
      "useBoardView.ts must use api.boards.getBoardView as its primary read path",
    ).toBe(true);
    expect(
      fileContains(/api\.tasks\.(list|search|listByBoard)|api\.steps\.(listAll|listByBoard)|api\.tasks\.countHitlPending|api\.tasks\.listDeleted/, content),
      "useBoardView.ts must not orchestrate board state from raw task/step counter queries",
    ).toBe(false);
  });
});

describe("Architecture: Component tests must mock hooks, not convex/react directly", () => {
  // Feature component test files in components/ directory must not import
  // useQuery/useMutation from convex/react. They should mock the feature hook
  // instead. Hook tests (in hooks/ or hooks/__tests__/) are the only place
  // where Convex mocks should appear.
  const targetTestFiles = [
    "TaskInput.test.tsx",
    "AgentConfigSheet.test.tsx",
    "SearchBar.test.tsx",
    "StepCard.test.tsx",
    "AgentSidebarItem.test.tsx",
  ];

  for (const testFile of targetTestFiles) {
    it(`components/${testFile} should not import from convex/react`, () => {
      const filePath = path.join(DASHBOARD_ROOT, "components", testFile);
      const content = readFileIfExists(filePath);
      if (!content) return;

      const hasConvexImport =
        /import\s+.*from\s+["']convex\/react["']/.test(content) ||
        /vi\.mock\(\s*["']convex\/react["']/.test(content);
      expect(
        hasConvexImport,
        `${testFile} must mock feature hooks instead of importing/mocking convex/react directly`,
      ).toBe(false);
    });
  }

  // Also check the tests/components/ directory for our target component tests
  const testsComponentsTargets = [
    "TagsPanel.test.tsx",
    "TaskInput.layout.test.tsx",
    "TaskInput.tags.test.tsx",
  ];

  for (const testFile of testsComponentsTargets) {
    it(`tests/components/${testFile} should not import from convex/react`, () => {
      const filePath = path.join(
        DASHBOARD_ROOT,
        "tests",
        "components",
        testFile,
      );
      const content = readFileIfExists(filePath);
      if (!content) return;

      const hasConvexImport =
        /import\s+.*from\s+["']convex\/react["']/.test(content) ||
        /vi\.mock\(\s*["']convex\/react["']/.test(content);
      expect(
        hasConvexImport,
        `tests/components/${testFile} must mock feature hooks instead of importing/mocking convex/react directly`,
      ).toBe(false);
    });
  }
});
