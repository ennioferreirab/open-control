import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CronJobsModal } from "./CronJobsModal";

const SAMPLE_JOB = {
  id: "abc123",
  name: "Check GitHub Stars",
  enabled: true,
  schedule: { kind: "every" as const, everyMs: 600000, atMs: null, expr: null, tz: null },
  payload: { kind: "agent_turn", message: "Check stars", deliver: true, channel: "whatsapp", to: "+1234567890" },
  state: {
    nextRunAtMs: Date.now() + 7200000,
    lastRunAtMs: Date.now() - 7200000,
    lastStatus: "ok" as const,
    lastError: null,
  },
  createdAtMs: 0,
  updatedAtMs: 0,
  deleteAfterRun: false,
};

function mockFetchWith(response: unknown, ok = true) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok,
    json: () => Promise.resolve(response),
  }));
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("CronJobsModal", () => {
  it("shows loading skeleton while fetching", () => {
    vi.stubGlobal("fetch", vi.fn(() => new Promise(() => {}))); // never resolves
    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    const skeletons = document.querySelectorAll(".animate-pulse");
    expect(skeletons.length).toBe(3);
  });

  it("renders job table with job data after fetch", async () => {
    mockFetchWith({ jobs: [SAMPLE_JOB] });
    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Check GitHub Stars")).toBeInTheDocument());
    expect(screen.getByText("every 10min")).toBeInTheDocument();
    expect(screen.getByText("whatsapp → +1234567890")).toBeInTheDocument();
    expect(screen.getByText("ok")).toBeInTheDocument();
  });

  it("shows empty state when no jobs returned", async () => {
    mockFetchWith({ jobs: [] });
    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByText(/No scheduled jobs/)).toBeInTheDocument()
    );
  });

  it("shows error state when fetch fails (non-ok response)", async () => {
    mockFetchWith({}, false);
    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByText("Failed to load cron jobs.")).toBeInTheDocument()
    );
  });

  it("shows error state when fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("network error")));
    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(screen.getByText("Failed to load cron jobs.")).toBeInTheDocument()
    );
  });

  it("calls onClose when X button is clicked", async () => {
    mockFetchWith({ jobs: [] });
    const onClose = vi.fn();
    render(<CronJobsModal open={true} onClose={onClose} />);
    const closeBtn = await screen.findByRole("button", { name: "Close cron jobs" });
    await userEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("does not fetch when modal is closed", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(<CronJobsModal open={false} onClose={vi.fn()} />);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("cancels in-flight fetch on close and does not update state", async () => {
    let resolveFetch!: (v: unknown) => void;
    vi.stubGlobal("fetch", vi.fn(() => new Promise((r) => { resolveFetch = r; })));
    const { rerender } = render(<CronJobsModal open={true} onClose={vi.fn()} />);
    // Close before fetch resolves
    rerender(<CronJobsModal open={false} onClose={vi.fn()} />);
    // Now resolve the fetch — should not update state (cancelled)
    resolveFetch({ ok: true, json: () => Promise.resolve({ jobs: [SAMPLE_JOB] }) });
    // Reopen with a new fetch that returns empty
    mockFetchWith({ jobs: [] });
    rerender(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() =>
      expect(screen.queryByText("Check GitHub Stars")).not.toBeInTheDocument()
    );
  });

  it("renders a trash button for each job row", async () => {
    mockFetchWith({ jobs: [SAMPLE_JOB] });
    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Check GitHub Stars")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: `Delete ${SAMPLE_JOB.name}` })).toBeInTheDocument();
  });

  it("clicking trash opens AlertDialog with the job name", async () => {
    mockFetchWith({ jobs: [SAMPLE_JOB] });
    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Check GitHub Stars")).toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: `Delete ${SAMPLE_JOB.name}` }));
    await waitFor(() =>
      expect(screen.getByRole("alertdialog")).toBeInTheDocument()
    );
    expect(screen.getByText(/Delete "Check GitHub Stars"/)).toBeInTheDocument();
    expect(screen.getByText("This action cannot be undone.")).toBeInTheDocument();
  });

  it("confirming delete calls DELETE endpoint and removes row from table", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ jobs: [SAMPLE_JOB] }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ success: true }) });
    vi.stubGlobal("fetch", fetchMock);

    render(<CronJobsModal open={true} onClose={vi.fn()} />);
    await waitFor(() => expect(screen.getByText("Check GitHub Stars")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: `Delete ${SAMPLE_JOB.name}` }));
    await waitFor(() => expect(screen.getByRole("alertdialog")).toBeInTheDocument());

    await userEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(screen.queryByText("Check GitHub Stars")).not.toBeInTheDocument()
    );
    expect(fetchMock).toHaveBeenCalledWith(`/api/cron/${SAMPLE_JOB.id}`, { method: "DELETE" });
  });
});
