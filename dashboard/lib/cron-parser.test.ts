import { describe, it, expect } from "vitest";
import { parseCronToTable } from "./cron-parser";

describe("parseCronToTable", () => {
  it("parses '0 9 * * 1-5' (weekday mornings)", () => {
    expect(parseCronToTable("0 9 * * 1-5")).toEqual({
      days: "Monday - Friday",
      hours: "9 AM",
      minutes: "At :00",
    });
  });

  it("parses '*/15 9-17 * * *' (every 15 min during business hours)", () => {
    expect(parseCronToTable("*/15 9-17 * * *")).toEqual({
      days: "Every day",
      hours: "9 AM - 5 PM",
      minutes: "Every 15 min",
    });
  });

  it("parses '30 14 * * 0' (Sunday afternoon)", () => {
    expect(parseCronToTable("30 14 * * 0")).toEqual({
      days: "Sunday",
      hours: "2 PM",
      minutes: "At :30",
    });
  });

  it("parses '0 0 * * *' (midnight every day)", () => {
    expect(parseCronToTable("0 0 * * *")).toEqual({
      days: "Every day",
      hours: "12 AM",
      minutes: "At :00",
    });
  });

  it("parses '0 12 * * *' (noon every day)", () => {
    expect(parseCronToTable("0 12 * * *")).toEqual({
      days: "Every day",
      hours: "12 PM",
      minutes: "At :00",
    });
  });

  it("parses '0,30 8,17 * * 1-5' (comma lists)", () => {
    expect(parseCronToTable("0,30 8,17 * * 1-5")).toEqual({
      days: "Monday - Friday",
      hours: "8 AM, 5 PM",
      minutes: "At :00, :30",
    });
  });

  it("parses '* * * * *' (every minute)", () => {
    expect(parseCronToTable("* * * * *")).toEqual({
      days: "Every day",
      hours: "Every hour",
      minutes: "Every min",
    });
  });

  it("returns null for malformed expression 'invalid'", () => {
    expect(parseCronToTable("invalid")).toBeNull();
  });

  it("returns null for too few fields '0 9 *'", () => {
    expect(parseCronToTable("0 9 *")).toBeNull();
  });

  it("returns null for 6-field expression '0 9 * * 1-5 2026'", () => {
    expect(parseCronToTable("0 9 * * 1-5 2026")).toBeNull();
  });

  it("handles day 7 as Sunday", () => {
    expect(parseCronToTable("0 9 * * 7")).toEqual({
      days: "Sunday",
      hours: "9 AM",
      minutes: "At :00",
    });
  });

  it("handles DOM/Month non-wildcard fields gracefully", () => {
    // DOM and month are not *, but parser still returns parsed result
    expect(parseCronToTable("0 9 15 6 1-5")).toEqual({
      days: "Monday - Friday",
      hours: "9 AM",
      minutes: "At :00",
    });
  });
});
