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
 * 5. Feature-first ownership lives under dashboard/features/ with
 *    per-feature components/hooks/lib boundaries.
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

function listFeatureFiles(featureName: string, subdir: "components" | "hooks"): string[] {
  const dir = path.join(DASHBOARD_ROOT, "features", featureName, subdir);
  if (!fs.existsSync(dir)) {
    return [];
  }

  return fs
    .readdirSync(dir)
    .filter((f: string) => f.endsWith(".ts") || f.endsWith(".tsx"))
    .filter((f: string) => !f.includes(".test."))
    .map((f: string) => path.join(dir, f));
}

const FEATURE_COMPONENT_DIRECT_CONVEX_IMPORT_EXCEPTIONS = new Set<string>();

const LEGACY_ROOT_COMPONENT_WRAPPERS = [
  "components/AgentConfigSheet.tsx",
  "components/AgentSidebarItem.tsx",
  "components/BoardSettingsSheet.tsx",
  "components/ExecutionPlanTab.tsx",
  "components/KanbanBoard.tsx",
  "components/ModelTierSettings.tsx",
  "components/SearchBar.tsx",
  "components/SettingsPanel.tsx",
  "components/StepCard.tsx",
  "components/TagsPanel.tsx",
  "components/TaskCard.tsx",
  "components/TaskDetailSheet.tsx",
  "components/TaskInput.tsx",
  "components/ThreadInput.tsx",
  "components/ThreadMessage.tsx",
] as const;

const LEGACY_ROOT_HOOK_WRAPPERS = [
  "hooks/useAgentConfigSheetData.ts",
  "hooks/useAgentSidebarItemState.ts",
  "hooks/useBoardView.ts",
  "hooks/usePlanEditorState.ts",
  "hooks/useSearchBarFilters.ts",
  "hooks/useTagsPanelData.ts",
  "hooks/useTaskDetailActions.ts",
  "hooks/useTaskDetailView.ts",
  "hooks/useTaskInputData.ts",
  "hooks/useThreadInputController.ts",
] as const;

const LEGACY_ROOT_COMPONENT_ALIAS_IMPORTS = [
  "@/components/AgentConfigSheet",
  "@/components/AgentSidebarItem",
  "@/components/BoardSettingsSheet",
  "@/components/ExecutionPlanTab",
  "@/components/KanbanBoard",
  "@/components/ModelTierSettings",
  "@/components/SearchBar",
  "@/components/SettingsPanel",
  "@/components/StepCard",
  "@/components/TagsPanel",
  "@/components/TaskCard",
  "@/components/TaskDetailSheet",
  "@/components/TaskInput",
  "@/components/ThreadInput",
  "@/components/ThreadMessage",
] as const;

const LEGACY_ROOT_HOOK_ALIAS_IMPORTS = [
  "@/hooks/useAgentConfigSheetData",
  "@/hooks/useAgentSidebarItemState",
  "@/hooks/useBoardView",
  "@/hooks/usePlanEditorState",
  "@/hooks/useSearchBarFilters",
  "@/hooks/useTagsPanelData",
  "@/hooks/useTaskDetailActions",
  "@/hooks/useTaskDetailView",
  "@/hooks/useTaskInputData",
  "@/hooks/useThreadInputController",
] as const;

describe("Architecture: feature shell exists for staged modularization", () => {
  it("dashboard/features/ README and first-wave feature directories exist", () => {
    expect(fs.existsSync(path.join(DASHBOARD_ROOT, "features"))).toBe(true);
    expect(fs.existsSync(path.join(DASHBOARD_ROOT, "features", "README.md"))).toBe(true);

    const featureDirs = [
      "tasks",
      "boards",
      "agents",
      "thread",
      "activity",
      "search",
      "settings",
      "terminal",
    ];

    for (const featureDir of featureDirs) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, "features", featureDir)),
        `features/${featureDir} should exist as a migration target`,
      ).toBe(true);
    }
  });

  it("tasks feature entry points exist in the feature-owned structure", () => {
    const requiredFiles = [
      "features/tasks/components/TaskDetailSheet.tsx",
      "features/tasks/components/TaskDetailThreadTab.tsx",
      "features/tasks/components/TaskDetailConfigTab.tsx",
      "features/tasks/components/TaskDetailFilesTab.tsx",
      "features/tasks/components/TaskInput.tsx",
      "features/tasks/components/ExecutionPlanTab.tsx",
      "features/tasks/components/TaskCard.tsx",
      "features/tasks/components/StepCard.tsx",
      "features/tasks/hooks/useTaskDetailView.ts",
      "features/tasks/hooks/useTaskDetailActions.ts",
      "features/tasks/hooks/useTaskInputData.ts",
      "features/tasks/hooks/usePlanEditorState.ts",
    ];

    for (const relativePath of requiredFiles) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, relativePath)),
        `${relativePath} should exist once the tasks entry-point migration begins`,
      ).toBe(true);
    }
  });

  it("boards and search feature entry points exist in the feature-owned structure", () => {
    const requiredFiles = [
      "features/boards/components/KanbanBoard.tsx",
      "features/boards/components/BoardSettingsSheet.tsx",
      "features/boards/hooks/useBoardView.ts",
      "features/search/components/SearchBar.tsx",
      "features/search/hooks/useSearchBarFilters.ts",
    ];

    for (const relativePath of requiredFiles) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, relativePath)),
        `${relativePath} should exist once the boards/search migration begins`,
      ).toBe(true);
    }
  });

  it("agents and settings feature entry points exist in the feature-owned structure", () => {
    const requiredFiles = [
      "features/agents/components/AgentSidebar.tsx",
      "features/agents/components/AgentConfigSheet.tsx",
      "features/agents/components/AgentSidebarItem.tsx",
      "features/agents/hooks/useAgentConfigSheetData.ts",
      "features/agents/hooks/useAgentSidebarData.ts",
      "features/agents/hooks/useAgentSidebarItemState.ts",
      "features/settings/components/SettingsPanel.tsx",
      "features/settings/components/ModelTierSettings.tsx",
      "features/settings/components/TagsPanel.tsx",
      "features/settings/hooks/useGatewaySleepModeRequest.ts",
      "features/settings/hooks/useTagsPanelData.ts",
    ];

    for (const relativePath of requiredFiles) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, relativePath)),
        `${relativePath} should exist once the agents/settings migration begins`,
      ).toBe(true);
    }
  });

  it("thread and activity feature entry points exist in the feature-owned structure", () => {
    const requiredFiles = [
      "features/thread/components/ThreadInput.tsx",
      "features/thread/components/ThreadMessage.tsx",
      "features/thread/lib/mentionNavigation.ts",
      "features/activity/components/ActivityFeed.tsx",
      "features/activity/components/ActivityFeedPanel.tsx",
      "features/activity/hooks/useActivityFeed.ts",
      "features/activity/hooks/useActivityFeedPanelState.ts",
      "features/thread/hooks/useThreadInputController.ts",
      "features/terminal/components/TerminalBoard.tsx",
      "features/terminal/hooks/useTerminalBoard.ts",
      "features/boards/hooks/useBoardProviderData.ts",
    ];

    for (const relativePath of requiredFiles) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, relativePath)),
        `${relativePath} should exist once the thread/activity migration begins`,
      ).toBe(true);
    }
  });
});

describe("Architecture: root wrapper cleanup stays converged", () => {
  it("legacy root component wrappers are deleted once feature ownership is canonical", () => {
    for (const relativePath of LEGACY_ROOT_COMPONENT_WRAPPERS) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, relativePath)),
        `${relativePath} should be deleted once the root wrapper cleanup lands`,
      ).toBe(false);
    }
  });

  it("legacy root hook wrappers are deleted once feature hooks become canonical", () => {
    for (const relativePath of LEGACY_ROOT_HOOK_WRAPPERS) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, relativePath)),
        `${relativePath} should be deleted once the root hook cleanup lands`,
      ).toBe(false);
    }
  });

  it("DashboardLayout imports canonical feature entry points directly", () => {
    const content = readFileIfExists(path.join(DASHBOARD_ROOT, "components", "DashboardLayout.tsx"));
    expect(content).not.toBeNull();
    expect(content).toContain(`from "@/features/agents/components/AgentSidebar"`);
    expect(content).toContain(`from "@/features/activity/components/ActivityFeedPanel"`);
    expect(content).toContain(`from "@/features/tasks/components/TaskInput"`);
    expect(content).toContain(`from "@/features/boards/components/KanbanBoard"`);
    expect(content).toContain(`from "@/features/terminal/components/TerminalBoard"`);
    expect(content).toContain(`from "@/features/tasks/components/TaskDetailSheet"`);
    expect(content).toContain(`from "@/features/settings/components/SettingsPanel"`);
    expect(content).toContain(`from "@/features/settings/components/TagsPanel"`);
    expect(content).toContain(`from "@/features/boards/components/BoardSettingsSheet"`);
    expect(content).toContain(`from "@/features/search/components/SearchBar"`);
    expect(content).toContain(`from "@/features/settings/hooks/useGatewaySleepModeRequest"`);
    expect(content).not.toContain(`from "@/components/AgentSidebar"`);
    expect(content).not.toContain(`from "@/components/ActivityFeedPanel"`);
    expect(content).not.toContain(`from "@/components/TerminalBoard"`);
    expect(content).not.toContain(`from "convex/react"`);
  });

  it("BoardContext consumes board provider data via a feature hook", () => {
    const content = readFileIfExists(path.join(DASHBOARD_ROOT, "components", "BoardContext.tsx"));
    expect(content).not.toBeNull();
    expect(content).toContain(`from "@/features/boards/hooks/useBoardProviderData"`);
    expect(content).not.toContain(`from "convex/react"`);
  });
});

describe("Architecture: story 22.4 hotspot seams exist", () => {
  it("dashboard/convex/lib contains split task hotspot owners", () => {
    const requiredFiles = [
      "convex/lib/taskMerge.ts",
      "convex/lib/taskDetailView.ts",
      "convex/lib/taskFiles.ts",
      "convex/lib/taskStatus.ts",
    ];

    for (const relativePath of requiredFiles) {
      expect(
        fs.existsSync(path.join(DASHBOARD_ROOT, relativePath)),
        `${relativePath} should exist as an internal owner extracted from convex/tasks.ts`,
      ).toBe(true);
    }
  });
});

describe("Architecture: task detail remains decomposed by tab ownership", () => {
  it("TaskDetailSheet delegates heavy tabs to extracted task-detail subcomponents", () => {
    const taskDetailSheetPath = path.join(
      DASHBOARD_ROOT,
      "features",
      "tasks",
      "components",
      "TaskDetailSheet.tsx",
    );
    const content = readFileIfExists(taskDetailSheetPath);
    expect(content).not.toBeNull();

    expect(content).toContain(`from "@/features/tasks/components/TaskDetailThreadTab"`);
    expect(content).toContain(`from "@/features/tasks/components/TaskDetailConfigTab"`);
    expect(content).toContain(`from "@/features/tasks/components/TaskDetailFilesTab"`);
  });
});

describe("Architecture: thread mention navigation uses a typed local contract", () => {
  it("AgentMentionAutocomplete depends on the feature-local mention navigation types", () => {
    const content = readFileIfExists(
      path.join(DASHBOARD_ROOT, "components", "AgentMentionAutocomplete.tsx"),
    );
    expect(content).not.toBeNull();
    expect(content).toContain(`from "@/features/thread/lib/mentionNavigation"`);
    expect(content).not.toContain(`as any).__mentionNav`);
  });
});

describe("Architecture: feature modules keep local boundaries", () => {
  const featureDirs = [
    "tasks",
    "boards",
    "agents",
    "thread",
    "activity",
    "search",
    "settings",
    "terminal",
  ];

  for (const featureDir of featureDirs) {
    it(`features/${featureDir}/components should not import convex/react directly`, () => {
      for (const filePath of listFeatureFiles(featureDir, "components")) {
        const relativePath = path.relative(DASHBOARD_ROOT, filePath);
        if (FEATURE_COMPONENT_DIRECT_CONVEX_IMPORT_EXCEPTIONS.has(relativePath)) {
          continue;
        }
        const content = readFileIfExists(filePath);
        if (!content) continue;
        expect(
          fileContainsDirectConvexImport(content),
          `${relativePath} must use feature hooks instead of direct convex/react imports`,
        ).toBe(false);
      }
    });

    it(`features/${featureDir}/hooks should not depend on feature UI components`, () => {
      for (const filePath of listFeatureFiles(featureDir, "hooks")) {
        const content = readFileIfExists(filePath);
        if (!content) continue;
        const componentImports = content
          .split("\n")
          .filter((line: string) =>
            new RegExp(`from\\s+["'].*features\\/${featureDir}\\/components\\/`).test(line),
          );
        expect(
          componentImports,
          `${path.relative(DASHBOARD_ROOT, filePath)} must not import feature UI components`,
        ).toEqual([]);
      }
    });

    it(`features/${featureDir} should not import legacy root aliases for feature-owned modules`, () => {
      for (const subdir of ["components", "hooks"] as const) {
        for (const filePath of listFeatureFiles(featureDir, subdir)) {
          const content = readFileIfExists(filePath);
          if (!content) continue;

          for (const importPath of LEGACY_ROOT_COMPONENT_ALIAS_IMPORTS) {
            expect(
              content.includes(importPath),
              `${path.relative(DASHBOARD_ROOT, filePath)} must not import ${importPath}`,
            ).toBe(false);
          }

          for (const importPath of LEGACY_ROOT_HOOK_ALIAS_IMPORTS) {
            expect(
              content.includes(importPath),
              `${path.relative(DASHBOARD_ROOT, filePath)} must not import ${importPath}`,
            ).toBe(false);
          }
        }
      }
    });
  }
});

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
      const content = fs.readFileSync(path.join(hooksDir, hookFile), "utf-8");
      // Allow imports from context providers (e.g. BoardContext) —
      // these are shared state hooks that happen to live in components/
      const lines = content
        .split("\n")
        .filter(
          (line: string) =>
            /from\s+["']@?\.?\.?\/?components\//.test(line) && !/Context["']/.test(line),
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
    const featureOwnedFilePath = path.join(
      DASHBOARD_ROOT,
      "features",
      "tasks",
      "hooks",
      "useTaskDetailView.ts",
    );
    const legacyFilePath = path.join(DASHBOARD_ROOT, "hooks", "useTaskDetailView.ts");
    const filePath = fs.existsSync(featureOwnedFilePath) ? featureOwnedFilePath : legacyFilePath;
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
    const featureOwnedFilePath = path.join(
      DASHBOARD_ROOT,
      "features",
      "boards",
      "hooks",
      "useBoardView.ts",
    );
    const legacyFilePath = path.join(DASHBOARD_ROOT, "hooks", "useBoardView.ts");
    const filePath = fs.existsSync(featureOwnedFilePath) ? featureOwnedFilePath : legacyFilePath;
    const content = readFileIfExists(filePath);
    if (!content) return;

    expect(
      fileContains(/api\.boards\.getBoardView/, content),
      "useBoardView.ts must use api.boards.getBoardView as its primary read path",
    ).toBe(true);
    expect(
      fileContains(
        /api\.tasks\.(list|search|listByBoard)|api\.steps\.(listAll|listByBoard)|api\.tasks\.countHitlPending|api\.tasks\.listDeleted/,
        content,
      ),
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
      const filePath = path.join(DASHBOARD_ROOT, "tests", "components", testFile);
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
