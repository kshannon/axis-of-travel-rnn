const SINCE_UNITS = [["d", 86_400], ["h", 3_600], ["min", 60]] as const;
const JUST_NOW = "just now";

/** An ISO timestamp as the time since, "3 h ago", just now under a minute. */
export function timeSince(stamp: string, now = Date.now()): string {
  const seconds = (now - Date.parse(stamp)) / 1000;
  const unit = SINCE_UNITS.find(([, size]) => seconds >= size);
  return unit ? `${Math.floor(seconds / unit[1])} ${unit[0]} ago` : JUST_NOW;
}

/** An ISO timestamp as local date and time to the minute. */
export function formatStamp(stamp: string): string {
  return new Date(stamp).toLocaleString("sv-SE", { dateStyle: "short", timeStyle: "short" });
}

/** A timestamp and the time since, or nothing for a missing timestamp. */
export function stampWithSince(stamp: string | null | undefined): string {
  return stamp ? `${formatStamp(stamp)} (${timeSince(stamp)})` : "";
}
