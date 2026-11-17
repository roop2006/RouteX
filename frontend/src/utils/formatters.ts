export function formatNumber(value: number, decimals = 0): string {
  if (isNaN(value)) return "0";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatSpeed(kmh: number | null | undefined): string {
  if (kmh == null || !Number.isFinite(kmh)) return "Unavailable";
  return `${Math.round(kmh)} km/h`;
}

export function formatDensity(density: number | null | undefined): string {
  if (density == null || !Number.isFinite(density)) return "Unavailable";
  const clamped = Math.max(0, Math.min(1, density));
  return `${Math.round(clamped * 100)}%`;
}

export function formatConfidence(confidence: number): string {
  if (isNaN(confidence)) return "0%";
  const clamped = Math.max(0, Math.min(1, confidence));
  return `${Math.round(clamped * 100)}%`;
}

export function formatTimestamp(isoString: string | null | undefined): string {
  if (!isoString) return "N/A";
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(isoString) ? isoString : `${isoString}Z`);
  if (isNaN(date.getTime())) return "Invalid date";
  return date.toLocaleString();
}

export function formatTimeOnly(isoString: string | null | undefined): string {
  if (!isoString) return "N/A";
  const date = new Date(/(?:Z|[+-]\d{2}:\d{2})$/.test(isoString) ? isoString : `${isoString}Z`);
  if (isNaN(date.getTime())) return "N/A";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
