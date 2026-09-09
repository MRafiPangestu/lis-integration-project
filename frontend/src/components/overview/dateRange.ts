// datetime-local range helpers — server-local naive strings ("YYYY-MM-DDTHH:mm"),
// never produced via toISOString(). Frontend-only UX convention; not API semantics.

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function toLocalInput(date: Date): string {
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

function startOfDay(offsetDays: number): Date {
  const now = new Date();
  return new Date(
    now.getFullYear(),
    now.getMonth(),
    now.getDate() + offsetDays,
    0,
    0,
    0,
    0,
  );
}

// Default: [today 00:00, tomorrow 00:00) — half-open, matches the API's [from, to).
export function todayRange(): [string, string] {
  return [toLocalInput(startOfDay(0)), toLocalInput(startOfDay(1))];
}

export function yesterdayRange(): [string, string] {
  return [toLocalInput(startOfDay(-1)), toLocalInput(startOfDay(0))];
}

export function last7DaysRange(): [string, string] {
  return [toLocalInput(startOfDay(-6)), toLocalInput(startOfDay(1))];
}

// "All" preset — a presentation-only sentinel window. The M8.4 endpoint requires
// both date bounds (omitting either returns 422), and Order.waktu_order is
// NOT NULL, so this window brackets every clinically representable timestamp.
// Literal server-local naive strings; no toISOString(), no Z, no offset.
export const ALL_DATE_FROM = "1900-01-01T00:00";
export const ALL_DATE_TO = "2999-12-31T23:59";

export function allRange(): [string, string] {
  return [ALL_DATE_FROM, ALL_DATE_TO];
}
