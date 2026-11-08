import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import html from '../index.html?raw';
import { addDays, weekendDates } from './filters';
import { messages } from './i18n';
import type { Position, Result } from './types';

const mocks = vi.hoisted(() => ({
  initAnalytics: vi.fn(),
  trackEvent: vi.fn(),
  map: {
    setOrigin: vi.fn(),
    setResults: vi.fn(),
    fitToResults: vi.fn(),
    highlight: vi.fn(),
    panTo: vi.fn(),
    invalidate: vi.fn(),
  },
  handlers: {
    onPick: vi.fn<(position: Position) => void>(),
    onSelect: vi.fn<(id: string) => void>(),
  },
}));

vi.mock('./analytics', () => ({
  initAnalytics: mocks.initAnalytics,
  trackEvent: mocks.trackEvent,
}));
vi.mock('./ui/map', () => ({
  ChurchMap: class {
    constructor(_element: HTMLElement, handlers: typeof mocks.handlers) {
      mocks.handlers = handlers;
      return mocks.map;
    }
  },
}));

const today = '2026-10-22';
const weekend = weekendDates(today);
const database = {
  churches: [
    {
      uuid: 'first',
      name: 'First Church',
      website: 'https://example.org',
      position: { latitude: 48.2, longitude: 16.3 },
      denomination: 'roman_catholic',
    },
    {
      uuid: 'second',
      name: 'Second Church',
      position: { latitude: 48.21, longitude: 16.31 },
      denomination: 'lutheran',
    },
  ],
  services: {
    first: [
      { date: today, start_time: '09:00', language: 'English' },
      { date: weekend[0], start_time: '10:00', language: 'German' },
    ],
    second: [{ date: addDays(today, 1), start_time: '11:00', language: 'German' }],
  },
};

function element<T extends HTMLElement>(selector: string): T {
  const found = document.querySelector<T>(selector);
  if (!found) throw new Error(`Missing test element ${selector}`);
  return found;
}

function change(selector: string, value: string): void {
  const input = element<HTMLInputElement | HTMLSelectElement>(selector);
  input.value = value;
  input.dispatchEvent(new Event('change'));
}

async function start(): Promise<void> {
  await import('./main');
  await vi.waitFor(() => expect(mocks.map.setResults).toHaveBeenCalled());
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 9, 22, 12));
  vi.resetModules();
  vi.clearAllMocks();
  localStorage.clear();
  const parsed = new DOMParser().parseFromString(html, 'text/html');
  document.head.innerHTML = parsed.head.innerHTML;
  document.body.innerHTML = parsed.body.innerHTML;
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => database }));
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('application flow', () => {
  it('loads data and combines search, day, language and denomination filters', async () => {
    await start();
    expect(element('.layout').dataset.view).toBe('map');
    expect(
      element<HTMLButtonElement>('.view-toggle [data-view="map"]').classList.contains('active'),
    ).toBe(true);
    expect(mocks.initAnalytics).toHaveBeenCalledOnce();
    expect(element('#status').textContent).toBe('1 church');
    expect(element('#results').textContent).toContain('First Church');
    expect(element<HTMLInputElement>('#date').value).toBe(today);
    expect(element<HTMLSelectElement>('#language').options).toHaveLength(3);

    element<HTMLButtonElement>('[data-day="any"]').click();
    change('#language', 'German');
    change('#denomination', 'lutheran');
    expect(element('#results').textContent).toContain('Second Church');
    expect(element('#results').textContent).not.toContain('First Church');
    const search = element<HTMLInputElement>('#name-search');
    search.value = 'first';
    search.dispatchEvent(new Event('input'));
    search.dispatchEvent(new Event('change'));
    expect(element('#results').textContent).toContain(messages.en.noServices);
    expect(mocks.trackEvent).toHaveBeenCalledWith('search_name');
    expect(mocks.trackEvent.mock.calls.flat()).not.toContain('first');
    expect(mocks.trackEvent).toHaveBeenCalledWith('filter_day_any');
    expect(mocks.trackEvent).toHaveBeenCalledWith('filter_language');
    expect(mocks.trackEvent).toHaveBeenCalledWith('filter_denomination');
  });

  it('switches weekend and custom dates, and retains filters when changing locale', async () => {
    await start();
    element<HTMLButtonElement>('[data-day="weekend"]').click();
    const weekendResults = mocks.map.setResults.mock.lastCall?.[0] as Result[];
    expect(weekendResults.map((result) => result.church.id)).toEqual(['first']);
    expect(weekendResults[0]?.services).toHaveLength(1);
    expect(
      weekendResults.every((result) => result.services.every((s) => weekend.includes(s.date))),
    ).toBe(true);
    expect(element('[data-day="weekend"]').classList.contains('active')).toBe(true);
    change('#date', addDays(today, 1));
    expect(element('[data-day="weekend"]').classList.contains('active')).toBe(false);
    change('#language', 'German');
    change('#ui-language', 'de');
    expect(document.documentElement.lang).toBe('de');
    expect(document.title).toBe(messages.de.title);
    expect(element('#locate').textContent).toBe(messages.de.useLocation);
    expect(element<HTMLInputElement>('#name-search').placeholder).toBe(messages.de.churchName);
    expect(element('#language').getAttribute('aria-label')).toBe(messages.de.serviceLanguage);
    expect(element<HTMLSelectElement>('#language').value).toBe('German');
    expect(localStorage.getItem('church-finder-locale')).toBe('de');
    expect(element('#results').textContent).toContain('Second Church');
  });

  it('coordinates map selection, location and view changes without sending coordinates to analytics', async () => {
    await start();
    const position = { latitude: 48.2, longitude: 16.3 };
    mocks.handlers.onPick(position);
    expect(mocks.map.setOrigin).toHaveBeenCalledWith(position);
    expect(element('#status').textContent).toContain(messages.en.yourPin);
    expect(mocks.trackEvent).toHaveBeenCalledWith('pin_location');
    element('.card').scrollIntoView = vi.fn();
    mocks.handlers.onSelect('first');
    expect(element('.card').classList.contains('active')).toBe(true);
    element<HTMLElement>('.card').click();
    expect(mocks.map.highlight).toHaveBeenCalledWith('first', true);
    element<HTMLButtonElement>('.view-toggle [data-view="map"]').click();
    expect(element('.layout').dataset.view).toBe('map');
    expect(mocks.map.invalidate).toHaveBeenCalledOnce();
    expect(mocks.trackEvent.mock.calls.flat()).not.toContain(position.latitude);
  });

  it('restores a saved locale on startup and translates the distance status on change', async () => {
    localStorage.setItem('church-finder-locale', 'it');
    await start();
    expect(element<HTMLSelectElement>('#ui-language').value).toBe('it');
    expect(document.title).toBe(messages.it.title);
    mocks.handlers.onPick({ latitude: 48.2, longitude: 16.3 });
    change('#ui-language', 'de');
    expect(element('#status').textContent).toContain(messages.de.yourPin);
    expect(element<HTMLSelectElement>('#language').options[0]?.textContent).toBe(
      messages.de.allLanguages,
    );
  });

  it('uses the browser location and reports a location failure', async () => {
    let succeed = true;
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((success, failure) => {
      if (succeed) {
        success({ coords: { latitude: 48.2, longitude: 16.3 } } as GeolocationPosition);
      } else {
        failure?.({} as GeolocationPositionError);
      }
    });
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    element<HTMLButtonElement>('#locate').click();
    expect(mocks.map.panTo).toHaveBeenCalledWith({ latitude: 48.2, longitude: 16.3 });
    expect(element('#status').textContent).toContain(messages.en.yourLocation);
    expect(getCurrentPosition).toHaveBeenCalledWith(expect.any(Function), expect.any(Function), {
      enableHighAccuracy: false,
      timeout: 10000,
    });
    succeed = false;
    element<HTMLButtonElement>('#locate').click();
    expect(element('#status').textContent).toBe(messages.en.geolocationFailed);
    expect(mocks.trackEvent).toHaveBeenCalledWith('use_location');
  });

  it('reports unsupported geolocation', async () => {
    vi.stubGlobal('navigator', { languages: ['en'] });
    await start();
    element<HTMLButtonElement>('#locate').click();
    expect(element('#status').textContent).toBe(messages.en.geolocationUnsupported);
  });

  it('shows load failures instead of rendering results', async () => {
    vi.mocked(fetch).mockResolvedValueOnce({ ok: false, status: 500 } as Response);
    await import('./main');
    await vi.waitFor(() => expect(element('#status').textContent).toBe(messages.en.loadFailed));
    expect(mocks.map.setResults).not.toHaveBeenCalled();
  });
});
