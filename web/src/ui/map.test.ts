import L from 'leaflet';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Result } from '../types';
import { ChurchMap } from './map';

afterEach(() => vi.restoreAllMocks());

describe('map popups', () => {
  it('omits unknown languages while retaining known languages and service times', () => {
    const element = document.createElement('div');
    document.body.append(element);
    const onSelect = vi.fn(() => map.fitToResults([result], result.church.position));
    const map = new ChurchMap(element, { onPick: vi.fn(), onSelect });
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
    expect(onSelect).toHaveBeenCalledWith('one');
    expect(element.querySelector('.leaflet-popup-content')?.textContent).toBe(
      'Church09:00 · 10:00 German',
    );
    element.remove();
  });

  describe('location framing', () => {
    it('fits the origin and the four nearest churches', () => {
      const fitBounds = vi.spyOn(L.Map.prototype, 'fitBounds');
      const element = document.createElement('div');
      document.body.append(element);
      const map = new ChurchMap(element, { onPick: vi.fn(), onSelect: vi.fn() });
      map.setOrigin({ latitude: 48.2, longitude: 16.3 });
      const results: Result[] = [0.001, 0.002, 0.003, 0.004, 0.005, 1].map((offset) => ({
        church: {
          id: String(offset),
          name: 'Church',
          website: '',
          position: { latitude: 48.2 + offset, longitude: 16.3 },
          religion: '',
          denomination: '',
          services: [],
        },
        services: [],
        distanceKm: null,
      }));
      map.fitToResults(results);
      const bounds = fitBounds.mock.calls[0]?.[0] as L.LatLngBounds;
      expect(bounds.getSouth()).toBeCloseTo(48.2);
      expect(bounds.getNorth()).toBeCloseTo(48.204);
      expect(fitBounds.mock.calls[0]?.[1]).toEqual(
        expect.objectContaining({ padding: [30, 30], maxZoom: 16, animate: false }),
      );
      fitBounds.mockClear();
      map.fitToResults([]);
      expect(fitBounds).not.toHaveBeenCalled();
      expect(map['map'].getCenter().lat).toBeCloseTo(48.2);
      expect(map['map'].getZoom()).toBe(13);
      element.remove();
    });

    it('keeps the pin and four nearest churches visible even in a dense area', () => {
      const element = document.createElement('div');
      Object.defineProperties(element, {
        clientWidth: { value: 800 },
        clientHeight: { value: 600 },
      });
      document.body.append(element);
      const map = new ChurchMap(element, { onPick: vi.fn(), onSelect: vi.fn() });
      map.setOrigin({ latitude: 48.2, longitude: 16.3 });
      const results: Result[] = [0.001, -0.001, 0.002, -0.002, 0.003, -0.003].map((offset) => ({
        church: {
          id: String(offset),
          name: 'Church',
          website: '',
          position: { latitude: 48.2 + offset, longitude: 16.3 },
          religion: '',
          denomination: '',
          services: [],
        },
        services: [],
        distanceKm: null,
      }));
      map.fitToResults(results);
      const leafletMap = map['map'];
      const bounds = leafletMap.getBounds();
      expect(bounds.contains([48.2, 16.3])).toBe(true);
      for (const { church } of results.slice(0, 4)) {
        expect(bounds.contains([church.position.latitude, church.position.longitude])).toBe(true);
      }
      expect(leafletMap.getZoom()).toBeLessThanOrEqual(16);
      element.remove();
    });

    it('includes distant churches when there are no matches nearby', () => {
      const element = document.createElement('div');
      Object.defineProperties(element, {
        clientWidth: { value: 800 },
        clientHeight: { value: 600 },
      });
      document.body.append(element);
      const map = new ChurchMap(element, { onPick: vi.fn(), onSelect: vi.fn() });
      map.setOrigin({ latitude: 47, longitude: 15 });
      const results: Result[] = [47.3, 47.4, 47.5, 47.6].map((latitude) => ({
        church: {
          id: String(latitude),
          name: 'Church',
          website: '',
          position: { latitude, longitude: 15 },
          religion: '',
          denomination: '',
          services: [],
        },
        services: [],
        distanceKm: null,
      }));
      map.fitToResults(results);
      const bounds = map['map'].getBounds();
      expect(bounds.contains([47, 15])).toBe(true);
      for (const { church } of results) {
        expect(bounds.contains([church.position.latitude, church.position.longitude])).toBe(true);
      }
      element.remove();
    });

    it('frames an explicitly selected church instead of the existing origin', () => {
      const element = document.createElement('div');
      Object.defineProperties(element, {
        clientWidth: { value: 800 },
        clientHeight: { value: 600 },
      });
      document.body.append(element);
      const map = new ChurchMap(element, { onPick: vi.fn(), onSelect: vi.fn() });
      map.setOrigin({ latitude: 47, longitude: 15 });
      const results: Result[] = [48.2, 48.21, 48.22, 48.23].map((latitude) => ({
        church: {
          id: String(latitude),
          name: 'Church',
          website: '',
          position: { latitude, longitude: 16.3 },
          religion: '',
          denomination: '',
          services: [],
        },
        services: [],
        distanceKm: null,
      }));
      map.fitToResults(results, { latitude: 48.2, longitude: 16.3 });
      const bounds = map['map'].getBounds();
      expect(bounds.contains([47, 15])).toBe(false);
      for (const { church } of results) {
        expect(bounds.contains([church.position.latitude, church.position.longitude])).toBe(true);
      }
      expect(map['map'].getZoom()).toBeLessThanOrEqual(16);
      element.remove();
    });
  });
});
