/** Convert a validated IANA civil day to a UTC half-open interval. */
export function localDayUtcBounds(timezone: string, localDay: string): {
  startUtc: string;
  endExclusiveUtc: string;
  durationHours: number;
} {
  if (typeof localDay !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(localDay)) {
    throw new Error('invalid_local_day');
  }
  const midnight = Date.parse(localDay + 'T00:00:00.000Z');
  if (!Number.isFinite(midnight) || new Date(midnight).toISOString().slice(0, 10) !== localDay ||
      localDay === '9999-12-31') {
    throw new Error('invalid_local_day');
  }
  if (typeof timezone !== 'string' || timezone.length === 0) throw new Error('invalid_timezone');
  let formatter: Intl.DateTimeFormat;
  try {
    formatter = new Intl.DateTimeFormat('en-US', {
      timeZone: timezone, year: 'numeric', month: '2-digit', day: '2-digit',
    });
  } catch {
    throw new Error('invalid_timezone');
  }
  const dateAt = (instant: number): string => {
    const parts = Object.fromEntries(formatter.formatToParts(new Date(instant))
      .filter(part => part.type === 'year' || part.type === 'month' || part.type === 'day')
      .map(part => [part.type, part.value]));
    return `${parts.year}-${parts.month}-${parts.day}`;
  };
  const firstInstant = (day: string, utcMidnight: number): number => {
    // Every IANA offset fits inside this bracket. Search for the first UTC
    // millisecond whose local calendar date is at least the requested date.
    let low = utcMidnight - 2 * 86_400_000;
    let high = utcMidnight + 2 * 86_400_000;
    while (low < high) {
      const middle = low + Math.floor((high - low) / 2);
      if (dateAt(middle) < day) low = middle + 1;
      else high = middle;
    }
    if (dateAt(low) !== day) throw new Error('invalid_local_day');
    return low;
  };
  const start = firstInstant(localDay, midnight);
  const nextMidnight = midnight + 86_400_000;
  const nextDay = new Date(nextMidnight).toISOString().slice(0, 10);
  const end = firstInstant(nextDay, nextMidnight);
  const iso = (instant: number): string => new Date(instant).toISOString().replace('.000Z', 'Z');
  return {startUtc: iso(start), endExclusiveUtc: iso(end),
    durationHours: (end - start) / 3_600_000};
}
