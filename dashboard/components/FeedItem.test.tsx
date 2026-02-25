import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { FeedItem } from "./FeedItem";

const baseActivity = {
  _id: "activity_1" as never,
  _creationTime: 1000,
  taskId: "task_1" as never,
  agentName: "test-agent",
  description: "Something happened",
  timestamp: "2026-01-01T12:00:00.000Z",
};

describe("FeedItem", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders step_completed event with green checkmark icon", () => {
    const { container } = render(
      <FeedItem
        activity={{ ...baseActivity, eventType: "step_completed" } as never}
      />
    );

    // CheckCircle2 icon is rendered — find by its SVG class h-3 w-3 text-green-500
    const icon = container.querySelector(".text-green-500");
    expect(icon).not.toBeNull();
    expect(screen.getByText("Something happened")).toBeInTheDocument();
  });

  it("renders step_crashed event with red border and X icon", () => {
    const { container } = render(
      <FeedItem
        activity={{ ...baseActivity, eventType: "step_crashed" } as never}
      />
    );

    // (a) the container has border-red-400 class
    const redBorderEl = container.querySelector(".border-red-400");
    expect(redBorderEl).not.toBeNull();

    // (b) the XCircle icon is rendered (text-red-500)
    const icon = container.querySelector(".text-red-500");
    expect(icon).not.toBeNull();
  });

  it("renders step_retrying event with amber refresh icon", () => {
    const { container } = render(
      <FeedItem
        activity={{ ...baseActivity, eventType: "step_retrying" } as never}
      />
    );

    // RefreshCw icon is rendered — has class text-amber-500
    const icon = container.querySelector(".text-amber-500");
    expect(icon).not.toBeNull();
  });

  it("renders task-level event without step icon", () => {
    const { container } = render(
      <FeedItem
        activity={{ ...baseActivity, eventType: "task_created" } as never}
      />
    );

    // No step icon classes should be rendered (no green, blue, amber, emerald, or slate icon)
    const icons = container.querySelectorAll(".h-3.w-3");
    expect(icons.length).toBe(0);
  });

  it("renders step_unblocked event without red border", () => {
    const { container } = render(
      <FeedItem
        activity={{ ...baseActivity, eventType: "step_unblocked" } as never}
      />
    );

    // The container must NOT have border-red-400
    const redBorder = container.querySelector(".border-red-400");
    expect(redBorder).toBeNull();

    // But it should have an icon (Unlock — text-emerald-500)
    const icon = container.querySelector(".text-emerald-500");
    expect(icon).not.toBeNull();
  });
});
