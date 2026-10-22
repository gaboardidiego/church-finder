import { describe, expect, it } from 'vitest';
import { formatDistance, haversineKm } from './geo';

describe('geo', () => {
  it('computes zero distance for the same point', () => {
    const p = { latitude: 48.2, longitude: 16.37 };
    expect(haversineKm(p, p)).toBe(0);
  });

  it('computes a known distance (Stephansdom to Schönbrunn ≈ 4.5 km)', () => {
    const km = haversineKm(
      { latitude: 48.2082, longitude: 16.3738 },
      { latitude: 48.1845, longitude: 16.3122 },
    );
    expect(km).toBeGreaterThan(4);
    expect(km).toBeLessThan(5.5);
  });

  it('formats distances', () => {
    expect(formatDistance(null)).toBe('');
    expect(formatDistance(0.45)).toBe('450 m');
    expect(formatDistance(2.345)).toBe('2.3 km');
  });
});
