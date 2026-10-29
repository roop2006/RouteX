export function formatNumber(value: number, decimals = 0): string {
  if (isNaN(value)) return "0";
  return value.toLocaleString(undefined, {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

export function formatSpeed(kmh: number): string {
  if (isNaN(kmh)) return "0 km/h";
  return `${Math.round(kmh)} km/h`;
}

export function formatDensity(density: number): string {
  if (isNaN(density)) return "0%";
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
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "Invalid date";
  return date.toLocaleString();
}

export function formatTimeOnly(isoString: string | null | undefined): string {
  if (!isoString) return "N/A";
  const date = new Date(isoString);
  if (isNaN(date.getTime())) return "N/A";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
