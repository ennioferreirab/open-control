import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { KanbanColumn } from "./KanbanColumn";

vi.mock("motion/react-client", () => ({
  div: ({ children, ...props }: React.PropsWithChildren<Record<string, unknown>>) => {
    const { layoutId, layout, transition, ...rest } = props;
    void layoutId;
    void layout;
    void transition;
    return <div {...rest}>{children}</div>;
  },
}));

vi.mock("@/features/boards/hooks/useKanbanColumnInteractions", () => ({
  useKanbanColumnInteractions: () => ({
    moveStep: vi.fn(),
    moveTask: vi.fn(),
  }),
}));

describe("KanbanColumn", () => {
  afterEach(() => {
    cleanup();
  });

  it("restores the light gray column background and border", () => {
    const { container } = render(
      <KanbanColumn
        title="Assigned"
        status="assigned"
        tasks={[]}
        stepGroups={[]}
        totalCount={0}
        accentColor="bg-cyan-500"
      />,
    );

    expect(screen.getByText("Assigned")).toBeInTheDocument();

    const column = container.firstElementChild;
    expect(column).not.toBeNull();
    expect(column?.className).toContain("bg-muted/40");
    expect(column?.className).toContain("border");
    expect(column?.className).toContain("border-border/70");
  });
});
