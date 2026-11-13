import { describe, expect, it, vi } from 'vitest';
import type { Result } from '../types';
import { ChurchMap } from './map';

describe('map popups', () => {
  it('omits unknown languages while retaining known languages and service times', () => {
    const element = document.createElement('div');
    document.body.append(element);
    const map = new ChurchMap(element, { onPick: vi.fn(), onSelect: vi.fn() });
    const result: Result = {
      church: {
        id: 'one',
        name: 'Church',
        website: '',
        position: { latitude: 48.2, longitude: 16.3 },
        religion: '',
        denomination: '',
        services: [],
      },
      services: [
        { date: '2026-10-24', startTime: '09:00', language: 'Unknown' },
        { date: '2026-10-24', startTime: '10:00', language: 'German' },
        { date: '2026-10-24', startTime: '', language: 'unknown' },
      ],
      distanceKm: null,
    };
    map.setResults([result]);
    element.querySelector<HTMLElement>('.church-marker')!.click();
    expect(element.querySelector('.leaflet-popup-content')?.textContent).toBe(
      'Church09:00 · 10:00 German',
    );
    element.remove();
  });
});
