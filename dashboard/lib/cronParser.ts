const DAY_NAMES = [
  "Sunday",
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
];

function formatHour(h: number): string {
  if (h === 0) return "12 AM";
  if (h < 12) return `${h} AM`;
  if (h === 12) return "12 PM";
  return `${h - 12} PM`;
}

function parseMinutesField(
  field: string
): string | null {
  if (field === "*") return "Every min";

  // */N
  const stepAll = field.match(/^\*\/(\d+)$/);
  if (stepAll) {
    const n = Number(stepAll[1]);
    if (n === 1) return "Every min";
    return `Every ${n} min`;
  }

  // Range with step: N-M/S
  const rangeStep = field.match(/^(\d+)-(\d+)\/(\d+)$/);
  if (rangeStep) {
    const [, start, end, step] = rangeStep;
    return `Every ${step} min :${start.padStart(2, "0")} - :${end.padStart(2, "0")}`;
  }

  // Range: N-M
  const range = field.match(/^(\d+)-(\d+)$/);
  if (range) {
    const [, start, end] = range;
    return `Every min :${start.padStart(2, "0")} - :${end.padStart(2, "0")}`;
  }

  // Comma-separated list
  if (field.includes(",")) {
    const parts = field.split(",");
    if (!parts.every((p) => /^\d+$/.test(p))) return null;
    return "At " + parts.map((p) => `:${p.padStart(2, "0")}`).join(", ");
  }

  // Single number
  if (/^\d+$/.test(field)) {
    const n = Number(field);
    if (n < 0 || n > 59) return null;
    return `At :${field.padStart(2, "0")}`;
  }

  return null;
}

function parseHoursField(field: string): string | null {
  if (field === "*") return "Every hour";

  // */N
  const stepAll = field.match(/^\*\/(\d+)$/);
  if (stepAll) {
    const n = Number(stepAll[1]);
    if (n === 1) return "Every hour";
    return `Every ${n} hours`;
  }

  // Range with step: H1-H2/S
  const rangeStep = field.match(/^(\d+)-(\d+)\/(\d+)$/);
  if (rangeStep) {
    const [, start, end, step] = rangeStep;
    return `Every ${step} hours ${formatHour(Number(start))} - ${formatHour(Number(end))}`;
  }

  // Range: H1-H2
  const range = field.match(/^(\d+)-(\d+)$/);
  if (range) {
    const [, start, end] = range;
    return `${formatHour(Number(start))} - ${formatHour(Number(end))}`;
  }

  // Comma-separated list
  if (field.includes(",")) {
    const parts = field.split(",");
    if (!parts.every((p) => /^\d+$/.test(p))) return null;
    return parts.map((p) => formatHour(Number(p))).join(", ");
  }

  // Single number
  if (/^\d+$/.test(field)) {
    const n = Number(field);
    if (n < 0 || n > 23) return null;
    return formatHour(n);
  }

  return null;
}

function parseDowField(field: string): string | null {
  if (field === "*") return "Every day";

  // Range: N-M
  const range = field.match(/^(\d+)-(\d+)$/);
  if (range) {
    const [, start, end] = range;
    const s = Number(start) === 7 ? 0 : Number(start);
    const e = Number(end) === 7 ? 0 : Number(end);
    if (s < 0 || s > 6 || e < 0 || e > 6) return null;
    return `${DAY_NAMES[s]} - ${DAY_NAMES[e]}`;
  }

  // Comma-separated list
  if (field.includes(",")) {
    const parts = field.split(",");
    if (!parts.every((p) => /^\d+$/.test(p))) return null;
    const names = parts.map((p) => {
      const n = Number(p) === 7 ? 0 : Number(p);
      if (n < 0 || n > 6) return null;
      return DAY_NAMES[n];
    });
    if (names.some((n) => n === null)) return null;
    return names.join(", ");
  }

  // Single number
  if (/^\d+$/.test(field)) {
    const n = Number(field) === 7 ? 0 : Number(field);
    if (n < 0 || n > 6) return null;
    return DAY_NAMES[n];
  }

  return null;
}

export function parseCronToTable(
  expr: string
): { days: string; hours: string; minutes: string } | null {
  const fields = expr.trim().split(/\s+/);
  if (fields.length !== 5) return null;

  const [minField, hourField, , , dowField] = fields;

  const minutes = parseMinutesField(minField);
  if (minutes === null) return null;

  const hours = parseHoursField(hourField);
  if (hours === null) return null;

  const days = parseDowField(dowField);
  if (days === null) return null;

  return { days, hours, minutes };
}
