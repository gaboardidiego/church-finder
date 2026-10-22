import { haversineKm } from './geo';
import type { Church, Filters, Position, Result } from './types';

export const ALL_LANGUAGES = '';

export const normalize = (text: string): string =>
  text
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .trim();

export function toIsoDate(date: Date): string {
  const pad = (n: number): string => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

export function addDays(iso: string, days: number): string {
  const [y = 0, m = 1, d = 1] = iso.split('-').map(Number);
  return toIsoDate(new Date(y, m - 1, d + days));
}

/** Saturday and Sunday of the current week (or today if already in the weekend). */
export function weekendDates(today: string): string[] {
  const [y = 0, m = 1, d = 1] = today.split('-').map(Number);
  const dow = new Date(y, m - 1, d).getDay();
  if (dow === 0) return [today];
  const saturday = addDays(today, 6 - dow);
  return [saturday, addDays(saturday, 1)];
}

export function collectLanguages(churches: Church[]): string[] {
  const set = new Set<string>();
  for (const church of churches) for (const s of church.services) set.add(s.language);
  return [...set].sort((a, b) => a.localeCompare(b));
}

export function applyFilters(
  churches: Church[],
  filters: Filters,
  origin: Position | null,
): Result[] {
  const query = normalize(filters.query);
  const results: Result[] = [];
  for (const church of churches) {
    if (query && !normalize(church.name).includes(query)) continue;
    const services = church.services.filter(
      (s) =>
        (filters.date === null || s.date === filters.date) &&
        (filters.language === ALL_LANGUAGES || s.language === filters.language),
    );
    const serviceFilterActive = filters.date !== null || filters.language !== ALL_LANGUAGES;
    if (serviceFilterActive && services.length === 0) continue;
    results.push({
      church,
      services,
      distanceKm: origin ? haversineKm(origin, church.position) : null,
    });
  }
  return results.sort((a, b) =>
    a.distanceKm !== null && b.distanceKm !== null
      ? a.distanceKm - b.distanceKm
      : a.church.name.localeCompare(b.church.name),
  );
}
