import { describe, expect, it } from 'vitest';
import {
  ALL_LANGUAGES,
  addDays,
  applyFilters,
  collectDenominations,
  collectLanguages,
  dateForDay,
  filterResults,
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
    const withUnknown = [
      ...churches,
      make('unknown', 'Unknown language', 48.2, [
        { date: '2026-10-24', startTime: '12:00', language: 'Unknown' },
        { date: '2026-10-24', startTime: '13:00', language: 'unknown' },
      ]),
    ];
    expect(collectLanguages(withUnknown)).toEqual(['English', 'German']);
    expect(
      applyFilters(
        withUnknown,
        { query: '', date: '2026-10-24', language: ALL_LANGUAGES, denomination: '' },
        null,
      ).map((result) => result.church.id),
    ).toContain('unknown');
  });

  it('computes dates', () => {
    expect(addDays('2026-10-31', 1)).toBe('2026-11-01');
    expect(weekendDates('2026-10-22')).toEqual(['2026-10-24', '2026-10-25']);
    expect(weekendDates('2026-10-24')).toEqual(['2026-10-24', '2026-10-25']);
    expect(weekendDates('2026-10-25')).toEqual(['2026-10-25']);
  });

  it('resolves day chips without changing custom dates', () => {
    expect(dateForDay('today', '2026-10-31')).toBe('2026-10-31');
    expect(dateForDay('tomorrow', '2026-10-31')).toBe('2026-11-01');
    expect(dateForDay('weekend', '2026-10-31')).toBeNull();
    expect(dateForDay('any', '2026-10-31')).toBeNull();
    expect(dateForDay('2026-11-03', '2026-10-31')).toBe('2026-11-03');
  });

  it('combines weekend services with language and denomination filters', () => {
    const mixed = [
      {
        ...churches[0]!,
        denomination: 'catholic',
        services: [
          { date: '2026-10-23', startTime: '08:00', language: 'English' },
          { date: '2026-10-24', startTime: '09:00', language: 'English' },
          { date: '2026-10-25', startTime: '10:00', language: 'German' },
        ],
      },
      { ...churches[1]!, denomination: 'lutheran' },
    ];
    const filters = {
      query: '',
      date: '2026-10-23',
      language: 'English',
      denomination: 'catholic',
    };
    const results = filterResults(mixed, filters, null, true, '2026-10-22');
    expect(results.map((result) => result.church.id)).toEqual(['far']);
    expect(results[0]?.services.map((service) => service.date)).toEqual(['2026-10-24']);
    expect(filters.date).toBe('2026-10-23');
    expect(filterResults(mixed, filters, null, false, '2026-10-22')[0]?.services[0]?.date).toBe(
      '2026-10-23',
    );
    expect(collectDenominations(mixed)).toEqual(['catholic', 'lutheran']);
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
