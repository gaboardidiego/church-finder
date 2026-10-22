import { describe, expect, it } from 'vitest';
import {
  ALL_LANGUAGES,
  addDays,
  applyFilters,
  collectLanguages,
  normalize,
  weekendDates,
} from './filters';
import type { Church } from './types';

const make = (id: string, name: string, lat: number, services: Church['services']): Church => ({
  id,
  name,
  website: '',
  religion: '',
  denomination: '',
  position: { latitude: lat, longitude: 16.37 },
  services,
});

const churches = [
  make('far', 'St. Étienne', 48.3, [
    { date: '2026-10-24', startTime: '10:00', language: 'German' },
  ]),
  make('near', 'Peterskirche', 48.21, [
    { date: '2026-10-24', startTime: '09:00', language: 'English' },
  ]),
  make('none', 'Empty', 48.22, []),
];

describe('filters', () => {
  it('normalizes accents and case', () => {
    expect(normalize('  Étienne ')).toBe('etienne');
  });

  it('filters by name ignoring accents', () => {
    const r = applyFilters(
      churches,
      { query: 'etienne', date: null, language: ALL_LANGUAGES, denomination: '' },
      null,
    );
    expect(r.map((x) => x.church.id)).toEqual(['far']);
  });

  it('filters by date and language, dropping churches without matching services', () => {
    const r = applyFilters(
      churches,
      { query: '', date: '2026-10-24', language: 'English', denomination: '' },
      null,
    );
    expect(r.map((x) => x.church.id)).toEqual(['near']);
    expect(
      applyFilters(
        churches,
        { query: '', date: '2026-10-30', language: '', denomination: '' },
        null,
      ),
    ).toEqual([]);
  });

  it('keeps churches without services when no service filter is active', () => {
    const r = applyFilters(
      churches,
      { query: '', date: null, language: '', denomination: '' },
      null,
    );
    expect(r).toHaveLength(3);
  });

  it('sorts by distance when an origin is given', () => {
    const r = applyFilters(
      churches,
      { query: '', date: null, language: '', denomination: '' },
      {
        latitude: 48.21,
        longitude: 16.37,
      },
    );
    expect(r.map((x) => x.church.id)).toEqual(['near', 'none', 'far']);
    expect(r[0]?.distanceKm).toBeCloseTo(0);
  });

  it('collects languages', () => {
    expect(collectLanguages(churches)).toEqual(['English', 'German']);
  });

  it('computes dates', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01');
    expect(weekendDates('2026-10-22')).toEqual(['2026-10-24', '2026-10-25']);
    expect(weekendDates('2026-10-25')).toEqual(['2026-10-25']);
  });
});

describe('denomination filter', () => {
  it('keeps only matching denominations', () => {
    const typed = [
      { ...churches[0]!, denomination: 'lutheran' },
      { ...churches[1]!, denomination: 'catholic' },
    ];
    const r = applyFilters(
      typed,
      { query: '', date: null, language: '', denomination: 'lutheran' },
      null,
    );
    expect(r.map((x) => x.church.denomination)).toEqual(['lutheran']);
  });
});
