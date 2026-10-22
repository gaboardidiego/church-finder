import type { Church, Service } from './types';

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

const str = (v: unknown): string => (typeof v === 'string' ? v.trim() : '');

function parseService(raw: unknown): Service | null {
  if (!isRecord(raw)) return null;
  const date = str(raw.date);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  return {
    date,
    startTime: str(raw.start_time),
    language: str(raw.language) || 'Unknown',
  };
}

/** Converts the raw database JSON into churches, skipping entries that cannot be used. */
export function parseDatabase(raw: unknown): Church[] {
  if (!isRecord(raw) || !Array.isArray(raw.churches)) return [];
  const servicesByChurch = isRecord(raw.services) ? raw.services : {};
  const churches: Church[] = [];
  for (const item of raw.churches) {
    if (!isRecord(item)) continue;
    const id = str(item.uuid);
    const pos = isRecord(item.position) ? item.position : {};
    const latitude = Number(pos.latitude);
    const longitude = Number(pos.longitude);
    if (!id || !Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;
    const rawServices = servicesByChurch[id];
    const services = (Array.isArray(rawServices) ? rawServices : [])
      .map(parseService)
      .filter((s): s is Service => s !== null)
      .sort((a, b) => a.date.localeCompare(b.date) || a.startTime.localeCompare(b.startTime));
    churches.push({
      id,
      name: str(item.name) || 'Unnamed church',
      website: str(item.website),
      position: { latitude, longitude },
      religion: str(item.religion),
      denomination: str(item.denomination),
      services,
    });
  }
  return churches;
}

export async function loadChurches(url: string): Promise<Church[]> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load data (${response.status})`);
  return parseDatabase(await response.json());
}
