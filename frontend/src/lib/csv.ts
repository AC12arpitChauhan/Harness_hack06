// Tiny client-side CSV export. No backend, no deps — builds a CSV string from
// rows and triggers a browser download.

export interface CsvColumn {
  key: string;
  label: string;
}

/** Quote a value only when it contains a comma, quote, or newline (RFC-4180). */
function escapeCell(value: unknown): string {
  const s = value === null || value === undefined ? "" : String(value);
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

/** Build a CSV string from rows, in the given column order/labels. */
export function toCsv(columns: CsvColumn[], rows: Record<string, unknown>[]): string {
  const head = columns.map((c) => escapeCell(c.label)).join(",");
  const body = rows.map((r) => columns.map((c) => escapeCell(r[c.key])).join(",")).join("\n");
  return `${head}\n${body}`;
}

/** Trigger a browser download of `content` as `filename`. */
export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
