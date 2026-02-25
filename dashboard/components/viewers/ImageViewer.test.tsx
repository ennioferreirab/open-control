import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ImageViewer } from "./ImageViewer";

describe("ImageViewer", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  const defaultProps = {
    blobUrl: "blob:http://localhost/test-image",
    filename: "test.png",
    onDownload: vi.fn(),
  };

  // Helper to simulate img onLoad with natural dimensions
  function simulateImageLoad(
    imgElement: HTMLImageElement,
    naturalWidth = 800,
    naturalHeight = 600,
  ) {
    Object.defineProperty(imgElement, "naturalWidth", { value: naturalWidth, configurable: true });
    Object.defineProperty(imgElement, "naturalHeight", { value: naturalHeight, configurable: true });
    fireEvent.load(imgElement);
  }

  it("renders image in fit mode by default", () => {
    render(<ImageViewer {...defaultProps} />);
    const img = screen.getByRole("img", { name: "test.png" });
    expect(img).toBeTruthy();
    expect(img.className).toContain("max-w-full");
    expect(img.className).toContain("max-h-full");
    expect(img.className).toContain("object-contain");
  });

  it("renders Fit button as active (secondary) and 1:1 button as ghost by default", () => {
    render(<ImageViewer {...defaultProps} />);
    const fitBtn = screen.getByRole("button", { name: /fit/i });
    const oneToOneBtn = screen.getByRole("button", { name: "1:1" });
    // Fit is active
    expect(fitBtn.className).toContain("secondary");
    // 1:1 is not active
    expect(oneToOneBtn.className).not.toContain("secondary");
  });

  it("zoom out button is disabled in fit mode", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomOutBtn = screen.getByRole("button", { name: "Zoom out" });
    expect(zoomOutBtn).toHaveAttribute("disabled");
  });

  it("zoom in button is not disabled in fit mode", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });
    expect(zoomInBtn).not.toHaveAttribute("disabled");
  });

  it("zoom in from fit mode sets scale to 1.0 (100%)", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });

    fireEvent.click(zoomInBtn);

    // After zoom in from fit, scale should be 1.0, showing 100%
    expect(screen.getByText("100%")).toBeTruthy();
  });

  it("Fit button resets scale to fit from numeric scale", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });
    const fitBtn = screen.getByRole("button", { name: /fit/i });

    // Zoom in to get to numeric scale
    fireEvent.click(zoomInBtn);
    expect(screen.getByText("100%")).toBeTruthy();

    // Click Fit to return
    fireEvent.click(fitBtn);
    expect(screen.queryByText("100%")).toBeNull();
    // Fit button should be active again
    expect(fitBtn.className).toContain("secondary");
  });

  it("1:1 button sets scale to 1.0", () => {
    render(<ImageViewer {...defaultProps} />);
    const oneToOneBtn = screen.getByRole("button", { name: "1:1" });

    fireEvent.click(oneToOneBtn);

    expect(screen.getByText("100%")).toBeTruthy();
    expect(oneToOneBtn.className).toContain("secondary");
  });

  it("zoom in increments through SCALES array", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });

    // fit -> 1.0 (100%)
    fireEvent.click(zoomInBtn);
    expect(screen.getByText("100%")).toBeTruthy();

    // 1.0 -> 1.25 (125%)
    fireEvent.click(zoomInBtn);
    expect(screen.getByText("125%")).toBeTruthy();

    // 1.25 -> 1.5 (150%)
    fireEvent.click(zoomInBtn);
    expect(screen.getByText("150%")).toBeTruthy();

    // 1.5 -> 2.0 (200%)
    fireEvent.click(zoomInBtn);
    expect(screen.getByText("200%")).toBeTruthy();
  });

  it("zoom out decrements through SCALES array, final zoom out returns to fit", () => {
    render(<ImageViewer {...defaultProps} />);

    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });
    const zoomOutBtn = screen.getByRole("button", { name: "Zoom out" });
    const fitBtn = screen.getByRole("button", { name: /fit/i });

    // Navigate from fit -> 1.0 -> 1.25, then zoom back down
    fireEvent.click(zoomInBtn); // fit -> 1.0
    expect(screen.getByText("100%")).toBeTruthy();

    fireEvent.click(zoomInBtn); // 1.0 -> 1.25
    expect(screen.getByText("125%")).toBeTruthy();

    // Zoom out: 1.25 -> 1.0
    fireEvent.click(zoomOutBtn);
    expect(screen.getByText("100%")).toBeTruthy();

    // Zoom out: 1.0 -> 0.75
    fireEvent.click(zoomOutBtn);
    expect(screen.getByText("75%")).toBeTruthy();

    // Zoom out: 0.75 -> 0.5
    fireEvent.click(zoomOutBtn);
    expect(screen.getByText("50%")).toBeTruthy();

    // Zoom out: 0.5 -> fit
    fireEvent.click(zoomOutBtn);
    expect(screen.queryByText("50%")).toBeNull();
    expect(fitBtn.className).toContain("secondary");
  });

  it("zoom in is disabled at maximum scale (2.0)", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });

    // Click zoom in multiple times to reach 2.0
    fireEvent.click(zoomInBtn); // fit -> 1.0
    fireEvent.click(zoomInBtn); // 1.0 -> 1.25
    fireEvent.click(zoomInBtn); // 1.25 -> 1.5
    fireEvent.click(zoomInBtn); // 1.5 -> 2.0

    expect(screen.getByText("200%")).toBeTruthy();
    expect(zoomInBtn).toHaveAttribute("disabled");
  });

  it("error state renders fallback message and Download button", () => {
    render(<ImageViewer {...defaultProps} />);
    const img = screen.getByRole("img", { name: "test.png" });

    fireEvent.error(img);

    expect(screen.getByText("Unable to display this image.")).toBeTruthy();
    expect(screen.getByRole("button", { name: /download/i })).toBeTruthy();
  });

  it("Download button in error state calls onDownload", () => {
    const onDownload = vi.fn();
    render(<ImageViewer {...defaultProps} onDownload={onDownload} />);
    const img = screen.getByRole("img", { name: "test.png" });

    fireEvent.error(img);

    const downloadBtn = screen.getByRole("button", { name: /download/i });
    fireEvent.click(downloadBtn);

    expect(onDownload).toHaveBeenCalledTimes(1);
  });

  it("scaled image has computed width/height from naturalSize (not CSS transform)", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });

    // Simulate onLoad on the fit-mode img to capture natural dimensions
    const fitImg = screen.getByRole("img", { name: "test.png" }) as HTMLImageElement;
    simulateImageLoad(fitImg, 800, 600);

    // Zoom in from fit to 1.0 — now scaled branch renders
    fireEvent.click(zoomInBtn);

    // The scaled img is now rendered; fire load on it too so naturalSize is confirmed
    const scaledImg = screen.getByRole("img", { name: "test.png" }) as HTMLImageElement;
    simulateImageLoad(scaledImg, 800, 600);

    // Should not use CSS transform
    expect(scaledImg.style.transform).toBeFalsy();

    // At scale 1.0 with naturalSize 800x600: width = 800px, height = 600px
    expect(scaledImg.style.width).toBe("800px");
    expect(scaledImg.style.height).toBe("600px");
  });

  it("fit-mode onLoad captures naturalSize so dimensions are available on scale switch", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });

    // Load the fit-mode image first (this stores naturalSize in state)
    const fitImg = screen.getByRole("img", { name: "test.png" }) as HTMLImageElement;
    simulateImageLoad(fitImg, 1024, 768);

    // Immediately switch to numeric scale — naturalSize should already be set
    fireEvent.click(zoomInBtn); // fit -> 1.0

    const scaledImg = screen.getByRole("img", { name: "test.png" }) as HTMLImageElement;

    // Since naturalSize was captured from fit-mode load, width/height should be set
    // at scale 1.0: 1024 * 1.0 = 1024, 768 * 1.0 = 768
    expect(scaledImg.style.width).toBe("1024px");
    expect(scaledImg.style.height).toBe("768px");
  });

  it("scaled image container has overflow-auto for scroll/pan", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });

    fireEvent.click(zoomInBtn); // fit -> 1.0

    // The outer image area div should have overflow-auto
    const img = screen.getByRole("img", { name: "test.png" });
    // Walk up to find the overflow-auto container
    let el: HTMLElement | null = img;
    let found = false;
    while (el) {
      if (el.className && el.className.includes("overflow-auto")) {
        found = true;
        break;
      }
      el = el.parentElement;
    }
    expect(found).toBe(true);
  });

  it("percentage label shows correct value for each scale", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });

    // From fit, zoom to 1.0
    fireEvent.click(zoomInBtn);
    expect(screen.getByText("100%")).toBeTruthy();

    // No percentage in fit mode (query by text should be null)
    const fitBtn = screen.getByRole("button", { name: /fit/i });
    fireEvent.click(fitBtn);
    expect(screen.queryByText("100%")).toBeNull();
  });

  it("percentage label is hidden in fit mode", () => {
    render(<ImageViewer {...defaultProps} />);
    // In fit mode (default), no percentage should be shown
    expect(screen.queryByText(/%/)).toBeNull();
  });

  it("zoom out disabled state updates correctly after leaving fit mode and returning", () => {
    render(<ImageViewer {...defaultProps} />);
    const zoomInBtn = screen.getByRole("button", { name: "Zoom in" });
    const zoomOutBtn = screen.getByRole("button", { name: "Zoom out" });
    const fitBtn = screen.getByRole("button", { name: /fit/i });

    // Initially disabled
    expect(zoomOutBtn).toHaveAttribute("disabled");

    // Zoom in — zoom out should now be enabled
    fireEvent.click(zoomInBtn);
    expect(zoomOutBtn).not.toHaveAttribute("disabled");

    // Return to fit — zoom out should be disabled again
    fireEvent.click(fitBtn);
    expect(zoomOutBtn).toHaveAttribute("disabled");
  });
});
