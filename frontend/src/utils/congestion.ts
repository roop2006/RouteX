export type CongestionStatus = "LOW" | "MEDIUM" | "HIGH" | "UNKNOWN";

export function normalizeCongestion(level: string | null | undefined): CongestionStatus {
  if (!level) return "UNKNOWN";
  const upper = level.toUpperCase();
  if (upper === "LOW" || upper === "MEDIUM" || upper === "HIGH") {
    return upper;
  }
  return "UNKNOWN";
}

export function getCongestionColor(level: string | null | undefined): string {
  const status = normalizeCongestion(level);
  switch (status) {
    case "LOW":
      return "#22c55e"; // green-500
    case "MEDIUM":
      return "#eab308"; // yellow-500
    case "HIGH":
      return "#ef4444"; // red-500
    default:
      return "#6b7280"; // gray-500
  }
}

export function getCongestionBadgeClass(level: string | null | undefined): string {
  const status = normalizeCongestion(level);
  switch (status) {
    case "LOW":
      return "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20 dark:bg-emerald-950/40 dark:text-emerald-400";
    case "MEDIUM":
      return "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20 dark:bg-amber-950/40 dark:text-amber-400";
    case "HIGH":
      return "bg-rose-50 text-rose-700 ring-1 ring-rose-600/20 dark:bg-rose-950/40 dark:text-rose-400";
    default:
      return "bg-slate-100 text-slate-700 ring-1 ring-slate-600/20 dark:bg-slate-800 dark:text-slate-300";
  }
}
