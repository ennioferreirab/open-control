import "@testing-library/jest-dom/vitest";

// jsdom does not implement ResizeObserver; provide a no-op stub so components
// that depend on it (e.g. @radix-ui/react-scroll-area) do not throw.
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};
