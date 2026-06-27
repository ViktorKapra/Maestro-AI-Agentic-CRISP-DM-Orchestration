// "house_prices" → "House Prices" — a presentable title for a dataset/case id.
export function prettyCase(id: string): string {
  return id.replace(/_/g, " ").replace(/\b\w/g, (ch) => ch.toUpperCase());
}

export function formatDuration(ms: number): string {
  const totalSeconds = Math.floor(ms / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;

  if (hours > 0) {
    return `${hours}h ${minutes}m ${seconds}s`;
  }
  if (minutes > 0) {
    return `${minutes}m ${seconds}s`;
  }
  return `${seconds}s`;
}
