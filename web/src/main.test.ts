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
  it('hides unknown language options and labels while retaining services', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          ...database,
          services: {
            ...database.services,
            first: [
              { date: today, start_time: '09:00' },
              { date: today, start_time: '10:00', language: 'German' },
            ],
          },
        }),
      }),
    );
    await start();
    expect(element('#language').textContent).not.toContain('Unknown');
    expect(element('#results').textContent).not.toContain('Unknown');
    expect(element('#results').textContent).toContain('09:00');
    expect(element('#results').textContent).toContain('10:00 · German');
    expect(element<HTMLSelectElement>('#language').options).toHaveLength(2);
  });

  it('loads data and combines search, day, language and denomination filters', async () => {
    await start();
    expect(element('.layout').dataset.view).toBe('map');
    expect(
      element<HTMLButtonElement>('.view-toggle [data-view="map"]').classList.contains('active'),
    ).toBe(true);
    expect(mocks.initAnalytics).toHaveBeenCalledOnce();
    expect(element('#status').textContent).toBe(messages.en.geolocationUnsupported);
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
    expect(mocks.map.fitToResults).toHaveBeenLastCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ church: expect.objectContaining({ id: 'first' }) }),
      ]),
      position,
    );
    element<HTMLElement>('.card').click();
    expect(mocks.map.highlight).toHaveBeenCalledWith('first');
    expect(mocks.map.fitToResults).toHaveBeenLastCalledWith(expect.any(Array), position);
    element<HTMLButtonElement>('.view-toggle [data-view="map"]').click();
    expect(element('.layout').dataset.view).toBe('map');
    expect(mocks.map.invalidate).toHaveBeenCalledOnce();
    expect(mocks.trackEvent.mock.calls.flat()).not.toContain(position.latitude);
  });

  it('frames churches around the selected church without changing the distance origin', async () => {
    await start();
    element<HTMLButtonElement>('[data-day="any"]').click();
    mocks.handlers.onPick({ latitude: 48.21, longitude: 16.31 });
    expect((mocks.map.setResults.mock.lastCall?.[0] as Result[])[0]?.church.id).toBe('second');
    mocks.map.setOrigin.mockClear();
    element<HTMLElement>('.card[data-id="first"]').click();
    const [results, focus] = mocks.map.fitToResults.mock.lastCall as [Result[], Position];
    expect(focus).toEqual({ latitude: 48.2, longitude: 16.3 });
    expect(results.map(({ church }) => church.id)).toEqual(['first', 'second']);
    expect(mocks.map.setOrigin).not.toHaveBeenCalled();
    expect(element('.card[data-id="first"]').classList.contains('active')).toBe(true);
    expect(element('#status').textContent).toContain(messages.en.yourPin);
  });

  it('does not replace a church selection with a late location response', async () => {
    let respond: PositionCallback | undefined;
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((success) => {
      respond = success;
    });
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    element<HTMLElement>('.card').click();
    respond?.({ coords: { latitude: 47, longitude: 15 } } as GeolocationPosition);
    expect(mocks.map.setOrigin).not.toHaveBeenCalled();
    expect(mocks.map.fitToResults.mock.lastCall?.[1]).toEqual({
      latitude: 48.2,
      longitude: 16.3,
    });
    expect(element('#status').textContent).toBe('1 church');
  });

  it('frames a church selected in list view once the map becomes visible', async () => {
    await start();
    element<HTMLButtonElement>('.view-toggle [data-view="list"]').click();
    mocks.map.fitToResults.mockClear();
    element<HTMLElement>('.card').click();
    expect(mocks.map.fitToResults).not.toHaveBeenCalled();
    element<HTMLButtonElement>('.view-toggle [data-view="map"]').click();
    expect(mocks.map.invalidate).toHaveBeenCalledTimes(2);
    expect(mocks.map.fitToResults).toHaveBeenLastCalledWith(expect.any(Array), {
      latitude: 48.2,
      longitude: 16.3,
    });
  });

  it('discards a pending list selection if filters remove that church', async () => {
    await start();
    element<HTMLButtonElement>('.view-toggle [data-view="list"]').click();
    element<HTMLElement>('.card').click();
    change('#date', addDays(today, 1));
    mocks.map.fitToResults.mockClear();
    element<HTMLButtonElement>('.view-toggle [data-view="map"]').click();
    expect(mocks.map.fitToResults).toHaveBeenLastCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ church: expect.objectContaining({ id: 'second' }) }),
      ]),
    );
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

  it('requests a network-capable location on startup and frames nearby results', async () => {
    const position = { latitude: 48.2, longitude: 16.3 };
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((success) =>
      success({ coords: position } as GeolocationPosition),
    );
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    expect(mocks.map.setOrigin).toHaveBeenCalledWith(position);
    expect(mocks.map.fitToResults.mock.lastCall?.[0][0].church.id).toBe('first');
    expect(element('#status').textContent).toContain(messages.en.yourLocation);
    expect(getCurrentPosition).toHaveBeenCalledWith(expect.any(Function), expect.any(Function), {
      enableHighAccuracy: false,
      maximumAge: 60000,
      timeout: 10000,
    });
    expect(mocks.trackEvent).not.toHaveBeenCalledWith('use_location');
    element<HTMLButtonElement>('#locate').click();
    expect(mocks.trackEvent).toHaveBeenCalledWith('use_location');
  });

  it('tries a cached approximate location after a positioning failure', async () => {
    const getCurrentPosition = vi
      .fn<Geolocation['getCurrentPosition']>()
      .mockImplementationOnce((_success, failure) =>
        failure?.({ code: 2 } as GeolocationPositionError),
      )
      .mockImplementationOnce((success) =>
        success({ coords: { latitude: 48.2, longitude: 16.3 } } as GeolocationPosition),
      );
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    expect(getCurrentPosition).toHaveBeenCalledTimes(2);
    expect(getCurrentPosition.mock.calls[1]?.[2]).toEqual({
      enableHighAccuracy: false,
      maximumAge: 24 * 60 * 60 * 1000,
      timeout: 5000,
    });
    expect(element('#status').textContent).toContain(messages.en.yourApproximateLocation);
  });

  it('labels low-accuracy browser locations as approximate', async () => {
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((success) =>
      success({
        coords: { latitude: 48.2, longitude: 16.3, accuracy: 1500 },
      } as GeolocationPosition),
    );
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    expect(element('#status').textContent).toContain(messages.en.yourApproximateLocation);
  });

  it('reports denied permission without retrying or hiding the failure after data loads', async () => {
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((_success, failure) =>
      failure?.({ code: 1 } as GeolocationPositionError),
    );
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    expect(getCurrentPosition).toHaveBeenCalledOnce();
    expect(element('#status').textContent).toBe(messages.en.geolocationFailed);
  });

  it('reports failure when both location attempts fail', async () => {
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((_success, failure) =>
      failure?.({ code: 2 } as GeolocationPositionError),
    );
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    expect(getCurrentPosition).toHaveBeenCalledTimes(2);
    expect(element('#status').textContent).toBe(messages.en.geolocationFailed);
  });

  it('does not replace a manually selected pin with a late location response', async () => {
    let respond: PositionCallback | undefined;
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((success) => {
      respond = success;
    });
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    const pin = { latitude: 47, longitude: 15 };
    mocks.handlers.onPick(pin);
    respond?.({ coords: { latitude: 48.2, longitude: 16.3 } } as GeolocationPosition);
    expect(mocks.map.setOrigin).toHaveBeenLastCalledWith(pin);
    expect(element('#status').textContent).toContain(messages.en.yourPin);
  });

  it('fits results when location arrives after the data', async () => {
    let respond: PositionCallback | undefined;
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((success) => {
      respond = success;
    });
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    expect(mocks.map.fitToResults).not.toHaveBeenCalled();
    respond?.({ coords: { latitude: 48.2, longitude: 16.3 } } as GeolocationPosition);
    expect(mocks.map.fitToResults.mock.lastCall?.[0][0].church.id).toBe('first');
    expect(element('#status').textContent).toContain(messages.en.yourLocation);
  });

  it('ignores a startup location response after a newer manual request', async () => {
    const callbacks: PositionCallback[] = [];
    const getCurrentPosition = vi.fn<Geolocation['getCurrentPosition']>((success) => {
      callbacks.push(success);
    });
    vi.stubGlobal('navigator', { languages: ['en'], geolocation: { getCurrentPosition } });
    await start();
    element<HTMLButtonElement>('#locate').click();
    callbacks[1]?.({ coords: { latitude: 47, longitude: 15 } } as GeolocationPosition);
    callbacks[0]?.({ coords: { latitude: 48, longitude: 16 } } as GeolocationPosition);
    expect(mocks.map.setOrigin).toHaveBeenLastCalledWith({ latitude: 47, longitude: 15 });
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
