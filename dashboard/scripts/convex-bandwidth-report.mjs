#!/usr/bin/env node

import { readFile, readdir, stat } from "node:fs/promises";
import { createInterface } from "node:readline/promises";
import { stdin as input } from "node:process";
import { basename, resolve } from "node:path";

const READ_FIELDS = ["database_read_bytes", "databaseReadBytes", "read_bytes", "readBytes"];
const WRITE_FIELDS = ["database_write_bytes", "databaseWriteBytes", "write_bytes", "writeBytes"];
const FUNCTION_FIELDS = [
  "function_name",
  "functionName",
  "function",
  "handler",
  "function_path",
  "functionPath",
  "name",
];
const TIME_FIELDS = ["timestamp", "ts", "time", "date", "created_at", "createdAt"];

function toNumber(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }
  return 0;
}

function pickField(record, fields) {
  for (const field of fields) {
    const value = record?.[field];
    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }
  return undefined;
}

function normalizeDate(value) {
  if (!value) {
    return "unknown";
  }
  const text = String(value);
  const date = new Date(text);
  if (!Number.isNaN(date.getTime())) {
    return date.toISOString().slice(0, 10);
  }
  return text.slice(0, 10) || "unknown";
}

function normalizeFunctionName(record) {
  const direct = pickField(record, FUNCTION_FIELDS);
  if (typeof direct === "string" && direct.trim()) {
    return direct.trim();
  }

  const nested = pickField(record, ["function", "handler", "metadata", "event"]) ?? record;
  if (nested && typeof nested === "object") {
    const nestedFunction = pickField(nested, FUNCTION_FIELDS);
    if (typeof nestedFunction === "string" && nestedFunction.trim()) {
      return nestedFunction.trim();
    }
  }

  return "unknown";
}

function coalesceLogRecord(line) {
  const trimmed = line.trim();
  if (!trimmed) {
    return null;
  }

  try {
    return JSON.parse(trimmed);
  } catch {
    return null;
  }
}

function normalizeRecords(inputRecords) {
  const rows = [];
  for (const item of inputRecords) {
    const record = typeof item === "string" ? coalesceLogRecord(item) : item;
    if (!record || typeof record !== "object") {
      continue;
    }

    const read = toNumber(pickField(record, READ_FIELDS));
    const write = toNumber(pickField(record, WRITE_FIELDS));
    if (read === 0 && write === 0) {
      continue;
    }

    rows.push({
      day: normalizeDate(pickField(record, TIME_FIELDS)),
      functionName: normalizeFunctionName(record),
      read,
      write,
    });
  }
  return rows;
}

async function* readJsonLinesFromFile(filePath) {
  const file = await readFile(filePath, "utf8");
  for (const line of file.split(/\r?\n/)) {
    if (line.trim()) {
      yield line;
    }
  }
}

async function* readJsonLinesFromStdin() {
  const rl = createInterface({ input, crlfDelay: Infinity });
  for await (const line of rl) {
    if (line.trim()) {
      yield line;
    }
  }
}

async function collectInputPaths(args) {
  const paths = args.length > 0 ? args : ["-"];
  const files = [];

  for (const arg of paths) {
    if (arg === "-") {
      files.push(arg);
      continue;
    }

    const fullPath = resolve(process.cwd(), arg);
    const info = await stat(fullPath);
    if (info.isDirectory()) {
      const entries = await readdir(fullPath);
      for (const entry of entries) {
        if (entry.endsWith(".jsonl") || entry.endsWith(".json")) {
          files.push(resolve(fullPath, entry));
        }
      }
      continue;
    }

    files.push(fullPath);
  }

  return files;
}

function formatBytes(bytes) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;
  let unit = units[0];
  for (const current of units) {
    unit = current;
    if (value < 1024) {
      break;
    }
    value /= 1024;
  }
  return `${value.toFixed(value >= 100 ? 0 : 2)} ${unit}`;
}

function renderReport(records, sourceLabel) {
  const byFunction = new Map();
  const byDay = new Map();
  let totalRead = 0;
  let totalWrite = 0;

  for (const record of records) {
    totalRead += record.read;
    totalWrite += record.write;

    const fnBucket = byFunction.get(record.functionName) ?? {
      read: 0,
      write: 0,
      days: new Map(),
    };
    fnBucket.read += record.read;
    fnBucket.write += record.write;
    fnBucket.days.set(
      record.day,
      (fnBucket.days.get(record.day) ?? 0) + record.read + record.write,
    );
    byFunction.set(record.functionName, fnBucket);

    const dayBucket = byDay.get(record.day) ?? { read: 0, write: 0, functions: new Map() };
    dayBucket.read += record.read;
    dayBucket.write += record.write;
    dayBucket.functions.set(
      record.functionName,
      (dayBucket.functions.get(record.functionName) ?? 0) + record.read + record.write,
    );
    byDay.set(record.day, dayBucket);
  }

  const functionRows = [...byFunction.entries()]
    .map(([functionName, bucket]) => ({
      functionName,
      read: bucket.read,
      write: bucket.write,
      total: bucket.read + bucket.write,
    }))
    .sort((left, right) => right.total - left.total || right.read - left.read);

  const dayRows = [...byDay.entries()]
    .map(([day, bucket]) => ({
      day,
      read: bucket.read,
      write: bucket.write,
      total: bucket.read + bucket.write,
    }))
    .sort((left, right) => left.day.localeCompare(right.day));

  const lines = [];
  lines.push(`# Convex Bandwidth Report`);
  lines.push("");
  lines.push(`Source: ${sourceLabel}`);
  lines.push(`Total reads: ${formatBytes(totalRead)}`);
  lines.push(`Total writes: ${formatBytes(totalWrite)}`);
  lines.push(`Total bandwidth: ${formatBytes(totalRead + totalWrite)}`);
  lines.push("");
  lines.push("## Hotspots");
  lines.push("");
  lines.push("| Function | Reads | Writes | Total |");
  lines.push("| --- | ---: | ---: | ---: |");
  for (const row of functionRows.slice(0, 20)) {
    lines.push(
      `| ${row.functionName} | ${formatBytes(row.read)} | ${formatBytes(row.write)} | ${formatBytes(row.total)} |`,
    );
  }

  lines.push("");
  lines.push("## Daily Totals");
  lines.push("");
  lines.push("| Day | Reads | Writes | Total |");
  lines.push("| --- | ---: | ---: | ---: |");
  for (const row of dayRows) {
    lines.push(
      `| ${row.day} | ${formatBytes(row.read)} | ${formatBytes(row.write)} | ${formatBytes(row.total)} |`,
    );
  }

  return lines.join("\n");
}

async function main() {
  const args = process.argv.slice(2);
  const paths = await collectInputPaths(args);
  const rawRecords = [];

  for (const path of paths) {
    if (path === "-") {
      for await (const line of readJsonLinesFromStdin()) {
        rawRecords.push(line);
      }
      continue;
    }
    for await (const line of readJsonLinesFromFile(path)) {
      rawRecords.push(line);
    }
  }

  const normalized = normalizeRecords(rawRecords);
  const sourceLabel = paths.length === 1 ? basename(paths[0]) : `${paths.length} sources`;
  process.stdout.write(renderReport(normalized, sourceLabel));
  process.stdout.write("\n");
}

main().catch((error) => {
  console.error(error instanceof Error ? (error.stack ?? error.message) : String(error));
  process.exit(1);
});
