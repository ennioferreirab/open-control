import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "./dialog";

describe("DialogContent", () => {
  afterEach(() => {
    cleanup();
  });

  it("does not rely on persistent translate centering classes", () => {
    render(
      <Dialog open>
        <DialogContent aria-describedby={undefined}>
          <DialogTitle>Dialog title</DialogTitle>
          <DialogDescription className="sr-only">Dialog description</DialogDescription>
          Dialog body
        </DialogContent>
      </Dialog>,
    );

    const content = screen.getByText("Dialog body").closest('[role="dialog"]') as HTMLElement;
    expect(content).toBeTruthy();
    expect(content.className).not.toContain("translate-x-[-50%]");
    expect(content.className).not.toContain("translate-y-[-50%]");
  });
});
