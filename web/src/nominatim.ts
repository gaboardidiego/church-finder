import type { Position } from './types';

const VIENNA_VIEWBOX = '16.18,48.32,16.58,48.11';

export interface Place {
  label: string;
  position: Position;
}

/** Geocodes via OpenStreetMap Nominatim (free; keep usage light: one request per user action). */
export async function searchPlace(query: string): Promise<Place | null> {
  const text = query.trim();
  if (!text) return null;
  const params = new URLSearchParams({
    q: text,
    format: 'jsonv2',
    limit: '1',
    viewbox: VIENNA_VIEWBOX,
    bounded: '1',
  });
  const response = await fetch(`https://nominatim.openstreetmap.org/search?${params}`);
  if (!response.ok) throw new Error(`Address search failed (${response.status})`);
  const data: unknown = await response.json();
  const first = Array.isArray(data) ? (data[0] as Record<string, unknown> | undefined) : undefined;
  if (!first) return null;
  const latitude = Number(first.lat);
  const longitude = Number(first.lon);
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
  return {
    label: typeof first.display_name === 'string' ? first.display_name : text,
    position: { latitude, longitude },
  };
}
