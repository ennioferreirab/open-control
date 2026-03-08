import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, act, cleanup } from "@testing-library/react";
import { useDocumentFetch } from "./useDocumentFetch";

// Mock URL.createObjectURL / revokeObjectURL (not available in jsdom)
const mockCreateObjectURL = vi.fn(() => "blob:http://localhost/mock-blob-id");
const mockRevokeObjectURL = vi.fn();

Object.defineProperty(URL, "createObjectURL", { value: mockCreateObjectURL, writable: true });
Object.defineProperty(URL, "revokeObjectURL", { value: mockRevokeObjectURL, writable: true });

const mockFetch = vi.fn();
global.fetch = mockFetch;

const textFile = { name: "readme.txt", subfolder: "attachments" };
const binaryFile = { name: "photo.png", subfolder: "output" };
const pdfFile = { name: "report.pdf", subfolder: "attachments" };

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error?: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("useDocumentFetch", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  // ---- Null file ----

  it("returns initial idle state when file is null", () => {
    const { result } = renderHook(() => useDocumentFetch("task_1", null));
    expect(result.current).toEqual({
      content: null,
      blobUrl: null,
      loading: false,
      error: null,
    });
  });

  it("does not call fetch when file is null", () => {
    renderHook(() => useDocumentFetch("task_1", null));
    expect(mockFetch).not.toHaveBeenCalled();
  });

  // ---- Text file fetch ----

  it("fetches text content for non-binary file extensions", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue("Hello, World!"),
      blob: vi.fn(),
    });

    const { result } = renderHook(() => useDocumentFetch("task_1", textFile));

    // Initially loading
    expect(result.current.loading).toBe(true);

    // Wait for fetch to complete
    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.content).toBe("Hello, World!");
    expect(result.current.blobUrl).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("constructs correct fetch URL for text file", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue("content"),
      blob: vi.fn(),
    });

    renderHook(() => useDocumentFetch("task_1", textFile));

    // fetch is called synchronously at start of effect
    expect(mockFetch).toHaveBeenCalledWith(
      "/api/tasks/task_1/files/attachments/readme.txt",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );

    // drain pending microtasks to avoid act() warnings
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  });

  it("URL-encodes filename in fetch URL", async () => {
    const fileWithSpaces = { name: "my file.txt", subfolder: "attachments" };
    mockFetch.mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue("content"),
      blob: vi.fn(),
    });

    renderHook(() => useDocumentFetch("task_1", fileWithSpaces));

    expect(mockFetch).toHaveBeenCalledWith(
      "/api/tasks/task_1/files/attachments/my%20file.txt",
      expect.objectContaining({
        signal: expect.any(AbortSignal),
      }),
    );

    // drain pending microtasks to avoid act() warnings
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });
  });

  // ---- Binary file fetch ----

  it("fetches blob URL for binary file extensions (png)", async () => {
    const mockBlob = new Blob(["binary"], { type: "image/png" });
    mockFetch.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(mockBlob),
      text: vi.fn(),
    });

    const { result } = renderHook(() => useDocumentFetch("task_1", binaryFile));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.blobUrl).toBe("blob:http://localhost/mock-blob-id");
    expect(result.current.content).toBeNull();
    expect(result.current.loading).toBe(false);
    expect(result.current.error).toBeNull();
    expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
  });

  it("fetches blob URL for pdf extension", async () => {
    const mockBlob = new Blob(["pdf-binary"], { type: "application/pdf" });
    mockFetch.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(mockBlob),
      text: vi.fn(),
    });

    const { result } = renderHook(() => useDocumentFetch("task_1", pdfFile));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.blobUrl).toBe("blob:http://localhost/mock-blob-id");
    expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
  });

  // ---- Error handling ----

  it("sets error on fetch failure (network error)", async () => {
    mockFetch.mockRejectedValue(new Error("Network error"));

    const { result } = renderHook(() => useDocumentFetch("task_1", textFile));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.error).toBe("Network error");
    expect(result.current.content).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("sets error on HTTP error status", async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 404,
      text: vi.fn(),
      blob: vi.fn(),
    });

    const { result } = renderHook(() => useDocumentFetch("task_1", textFile));

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.error).toBe("HTTP 404");
    expect(result.current.loading).toBe(false);
  });

  // ---- Blob URL cleanup ----

  it("revokes blob URL when hook unmounts", async () => {
    const mockBlob = new Blob(["binary"], { type: "image/png" });
    mockFetch.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(mockBlob),
      text: vi.fn(),
    });

    const { unmount } = renderHook(() => useDocumentFetch("task_1", binaryFile));

    await act(async () => {
      await Promise.resolve();
    });

    unmount();

    expect(mockRevokeObjectURL).toHaveBeenCalledWith("blob:http://localhost/mock-blob-id");
  });

  it("revokes old blob URL when file changes", async () => {
    const mockBlob = new Blob(["binary"], { type: "image/png" });
    mockFetch.mockResolvedValue({
      ok: true,
      blob: vi.fn().mockResolvedValue(mockBlob),
      text: vi.fn(),
    });

    const { rerender } = renderHook(
      ({ file }: { file: { name: string; subfolder: string } | null }) =>
        useDocumentFetch("task_1", file),
      { initialProps: { file: binaryFile } },
    );

    await act(async () => {
      await Promise.resolve();
    });

    // Change to a different file — should revoke old blob URL
    mockFetch.mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue("new content"),
      blob: vi.fn(),
    });

    rerender({ file: textFile });

    await act(async () => {
      await Promise.resolve();
    });

    expect(mockRevokeObjectURL).toHaveBeenCalledWith("blob:http://localhost/mock-blob-id");
  });

  // ---- State reset on file change ----

  it("resets content and blobUrl to null when file changes", async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      text: vi.fn().mockResolvedValue("file 1 content"),
      blob: vi.fn(),
    });

    const { result, rerender } = renderHook(
      ({ file }: { file: { name: string; subfolder: string } | null }) =>
        useDocumentFetch("task_1", file),
      { initialProps: { file: textFile as { name: string; subfolder: string } | null } },
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(result.current.content).toBe("file 1 content");

    // Change to null
    rerender({ file: null });

    expect(result.current.content).toBeNull();
    expect(result.current.blobUrl).toBeNull();
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });

  it("aborts the in-flight request when the hook unmounts", () => {
    const fetchDeferred = deferred<Response>();
    mockFetch.mockReturnValue(fetchDeferred.promise);

    const { unmount } = renderHook(() => useDocumentFetch("task_1", textFile));

    const [, init] = mockFetch.mock.calls[0] as [string, { signal?: AbortSignal } | undefined];
    expect(init?.signal).toBeDefined();
    expect(init?.signal?.aborted).toBe(false);

    unmount();

    expect(init?.signal?.aborted).toBe(true);
    fetchDeferred.reject(new Error("aborted"));
  });

  it("ignores stale responses when the file changes mid-request", async () => {
    const firstFetch = deferred<{
      ok: boolean;
      text: () => Promise<string>;
      blob: () => Promise<Blob>;
    }>();
    const secondFetch = deferred<{
      ok: boolean;
      text: () => Promise<string>;
      blob: () => Promise<Blob>;
    }>();

    mockFetch.mockReturnValueOnce(firstFetch.promise).mockReturnValueOnce(secondFetch.promise);

    const { result, rerender } = renderHook(
      ({ file }: { file: { name: string; subfolder: string } | null }) =>
        useDocumentFetch("task_1", file),
      { initialProps: { file: textFile as { name: string; subfolder: string } | null } },
    );

    rerender({ file: { name: "fresh.txt", subfolder: "attachments" } });

    await act(async () => {
      secondFetch.resolve({
        ok: true,
        text: vi.fn().mockResolvedValue("fresh content"),
        blob: vi.fn(),
      });
      await Promise.resolve();
    });

    expect(result.current.content).toBe("fresh content");

    await act(async () => {
      firstFetch.resolve({
        ok: true,
        text: vi.fn().mockResolvedValue("stale content"),
        blob: vi.fn(),
      });
      await Promise.resolve();
    });

    expect(result.current.content).toBe("fresh content");
    expect(result.current.error).toBeNull();
    expect(result.current.loading).toBe(false);
  });
});
