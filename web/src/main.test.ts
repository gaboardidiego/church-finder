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
    showApproximateLocation: vi.fn(),
    focusChurch: vi.fn(),
    highlight: vi.fn(),
    invalidate: vi.fn(),
    updateSchedule: vi.fn(),
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

async function start(italyResponse?: Promise<Response>): Promise<void> {
  const currentFetch = globalThis.fetch;
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init?: RequestInit) =>
      url.includes('churches_italy.database.json')
        ? (italyResponse ??
          Promise.resolve({ ok: true, json: async () => ({ churches: [], services: {} }) }))
        : currentFetch(url, init),
    ),
  );
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
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) =>
      url === 'https://ipwho.is/'
        ? new Promise<Response>(() => {})
        : Promise.resolve({ ok: true, json: async () => database }),
    ),
  );
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('application flow', () => {
  it('debounces name searches without losing the final query', async () => {
    await start();
    mocks.map.setResults.mockClear();
    const search = element<HTMLInputElement>('#name-search');
    for (const value of ['s', 'se', 'second']) {
      search.value = value;
      search.dispatchEvent(new Event('input'));
    }
    expect(mocks.map.setResults).not.toHaveBeenCalled();
    await vi.waitFor(() => expect(mocks.map.setResults).toHaveBeenCalledOnce());
    const results = mocks.map.setResults.mock.lastCall?.[0] as Result[];
    expect(results).toEqual([]);
    element<HTMLButtonElement>('[data-day="any"]').click();
    expect((mocks.map.setResults.mock.lastCall?.[0] as Result[])[0]?.church.id).toBe('second');
  });

  it('updates only cards and popups belonging to the loaded region', async () => {
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        observe() {}
        disconnect() {}
      },
    );
    const indexed = {
      churches: database.churches.map((church, index) => ({
        ...church,
        region: index === 0 ? 'wien' : 'tirol',
        service_index: [{ date: today, language: 'English' }],
      })),
      service_files: { wien: 'services-wien-abcd.json', tirol: 'services-tirol-abcd.json' },
      services: {},
    };
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) => {
        if (url === 'https://ipwho.is/') return new Promise<Response>(() => {});
        return Promise.resolve({
          ok: true,
          json: async () =>
            url.includes('services-wien-')
              ? { services: { first: [database.services.first[0]] } }
              : indexed,
        });
      }),
    );
    await start();
    element<HTMLButtonElement>('.view-toggle [data-view="list"]').click();
    const first = element<HTMLElement>('.card[data-id="first"]');
    const second = element<HTMLElement>('.card[data-id="second"]');
    mocks.map.updateSchedule.mockClear();
    first.click();
    await vi.waitFor(() => expect(first.textContent).toContain('09:00'));
    expect(element('.card[data-id="first"]')).toBe(first);
    expect(element('.card[data-id="second"]')).toBe(second);
    expect(
      mocks.map.updateSchedule.mock.calls.map(([result]) => (result as Result).church.id),
    ).toEqual(['first', 'first']);
  });

  it('credits Ember before any Italy records have been imported', async () => {
    await start();
    const link = element<HTMLAnchorElement>('#italy-source');
    expect(link.href).toBe('https://ember.dpgu.me/app/');
    expect(link.textContent).toBe('Ember');
  });

  it('credits Ember when its Italy index is loaded', async () => {
    const italy = {
      churches: [
        {
          ...database.churches[0],
          uuid: 'italian',
          schedule_source: 'ember',
          last_verified_at: '2020-08-03',
        },
      ],
      services: { italian: database.services.first },
    };
    await start(Promise.resolve({ ok: true, json: async () => italy } as Response));
    const link = element<HTMLAnchorElement>('#italy-source');
    expect(link.href).toBe('https://ember.dpgu.me/app/');
    expect(link.textContent).toBe('Ember');
    expect(element('#results').textContent).toContain('Schedule last verified: 2020-08-03');
  });

  it('retains the original source credit for a restored legacy Italy index', async () => {
    const italy = {
      churches: [
        {
          ...database.churches[0],
          uuid: 'italian',
          region: 'italy-example',
          service_index: [],
        },
      ],
      service_files: { 'italy-example': 'services-italy-example-abcd.json' },
      services: {},
    };
    await start(Promise.resolve({ ok: true, json: async () => italy } as Response));
    const link = element<HTMLAnchorElement>('#italy-source');
    expect(link.href).toBe('https://orarimesse.it/');
    expect(link.textContent).toBe('OrariMesse.it');
  });

  it('shows Austrian results with an explicit warning when the Italy index fails', async () => {
    const error = vi.spyOn(console, 'error').mockImplementation(() => {});
    await start(Promise.resolve({ ok: false, status: 503 } as Response));
    expect(element('#results').textContent).toContain('First Church');
    expect(element('#status').textContent).toBe(messages.en.partialLoadFailed);
    expect(error).toHaveBeenCalledOnce();
  });

  it('filters indexed schedules without requests and lazily loads visible cards', async () => {
    let observerCallback: IntersectionObserverCallback | undefined;
    vi.stubGlobal(
      'IntersectionObserver',
      class {
        constructor(callback: IntersectionObserverCallback) {
          observerCallback = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
    const indexed = {
      churches: [
        {
          ...database.churches[0],
          region: 'wien',
          service_index: [
            { date: today, language: 'English' },
            { date: weekend[0], language: 'German' },
          ],
        },
        {
          ...database.churches[1],
          region: 'tirol',
          service_index: [{ date: weekend[0], language: 'English' }],
        },
      ],
      service_files: { wien: 'services-wien-abcd.json', tirol: 'services-tirol-1234.json' },
      services: {},
    };
    const fetch = vi.fn((url: string) => {
      if (url === 'https://ipwho.is/') return new Promise<Response>(() => {});
      if (url.includes('services-wien-'))
        return Promise.resolve({ ok: true, json: async () => ({ services: database.services }) });
      return Promise.resolve({ ok: true, json: async () => indexed });
    });
    vi.stubGlobal('fetch', fetch);
    await start();
    expect(fetch.mock.calls.filter(([url]) => url.includes('/services-'))).toHaveLength(0);
    expect(element<HTMLSelectElement>('#language').options).toHaveLength(3);
    element<HTMLButtonElement>('[data-day="weekend"]').click();
    change('#language', 'German');
    expect(element('#results').textContent).toContain('First Church');
    expect(element('#results').textContent).not.toContain('Second Church');
    element<HTMLButtonElement>('.view-toggle [data-view="list"]').click();
    const card = element('.card');
    expect(card.textContent).toContain(messages.en.schedulesPending);
    observerCallback?.(
      [{ target: card, isIntersecting: true } as unknown as IntersectionObserverEntry],
      {} as IntersectionObserver,
    );
    await vi.waitFor(() => expect(element('.card').textContent).toContain('10:00'));
    expect(fetch.mock.calls.filter(([url]) => url.includes('/services-'))).toHaveLength(1);
    expect(mocks.map.updateSchedule).toHaveBeenCalled();
  });

  it('loads selected map schedules, shows failures and retries without restoring stale filters', async () => {
    const indexed = {
      churches: [
        {
          ...database.churches[0],
          region: 'wien',
          service_index: [{ date: today, language: 'English' }],
        },
      ],
      service_files: { wien: 'services-wien-abcd.json' },
      services: {},
    };
    let resolveRetry: ((value: { ok: boolean; json: () => Promise<object> }) => void) | undefined;
    let attempts = 0;
    const fetch = vi.fn((url: string) => {
      if (url === 'https://ipwho.is/') return new Promise<Response>(() => {});
      if (url.includes('services-wien-')) {
        attempts++;
        if (attempts === 1) return Promise.resolve({ ok: false, status: 500 });
        return new Promise<{ ok: boolean; json: () => Promise<object> }>((resolve) => {
          resolveRetry = resolve;
        });
      }
      return Promise.resolve({ ok: true, json: async () => indexed });
    });
    vi.stubGlobal('fetch', fetch);
    await start();
    element<HTMLElement>('.card').scrollIntoView = vi.fn();
    mocks.handlers.onSelect('first');
    await vi.waitFor(() =>
      expect(element('.card').textContent).toContain(messages.en.schedulesFailed),
    );
    element<HTMLButtonElement>('.card button').click();
    expect(element('.card').textContent).toContain(messages.en.schedulesLoading);
    const search = element<HTMLInputElement>('#name-search');
    search.value = 'no match';
    search.dispatchEvent(new Event('input'));
    resolveRetry?.({
      ok: true,
      json: async () => ({ services: { first: [database.services.first[0]] } }),
    });
    await vi.waitFor(() => expect(attempts).toBe(2));
    await vi.waitFor(() =>
      expect(element('#results').textContent).toContain(messages.en.noServices),
    );
    expect(element('#results').textContent).not.toContain('First Church');
  });

  it('loads only viewport cards without IntersectionObserver', async () => {
    vi.stubGlobal('IntersectionObserver', undefined);
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (
      this: HTMLElement,
    ) {
      const top = this.dataset.id === 'second' ? 200 : 0;
      return { top, bottom: top + 100, height: 100 } as DOMRect;
    });
    const indexed = {
      churches: database.churches.map((church, index) => ({
        ...church,
        region: index === 0 ? 'wien' : 'tirol',
        service_index: [{ date: today, language: 'English' }],
      })),
      service_files: { wien: 'services-wien-abcd.json', tirol: 'services-tirol-abcd.json' },
      services: {},
    };
    const fetch = vi.fn((url: string) => {
      if (url === 'https://ipwho.is/' || url.includes('/services-'))
        return new Promise<Response>(() => {});
      return Promise.resolve({ ok: true, json: async () => indexed });
    });
    vi.stubGlobal('fetch', fetch);
    await start();
    element<HTMLButtonElement>('.view-toggle [data-view="list"]').click();
    expect(
      fetch.mock.calls.filter(([url]) => url.includes('/services-')).map(([url]) => url),
    ).toEqual([expect.stringContaining('services-wien-abcd.json')]);
  });

  it('hides unknown language options and labels while retaining services', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        url === 'https://ipwho.is/'
          ? new Promise<Response>(() => {})
          : Promise.resolve({
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
      ),
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
    expect(mocks.map.focusChurch).toHaveBeenLastCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ church: expect.objectContaining({ id: 'first' }) }),
      ]),
      position,
    );
    element<HTMLElement>('.card').click();
    expect(mocks.map.highlight).toHaveBeenCalledWith('first');
    expect(mocks.map.focusChurch).toHaveBeenLastCalledWith(expect.any(Array), position);
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
    const [results, focus] = mocks.map.focusChurch.mock.lastCall as [Result[], Position];
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
    expect(mocks.map.focusChurch.mock.lastCall?.[1]).toEqual({
      latitude: 48.2,
      longitude: 16.3,
    });
    expect(element('#status').textContent).toBe('1 church');
  });

  it('frames a church selected in list view once the map becomes visible', async () => {
    await start();
    element<HTMLButtonElement>('.view-toggle [data-view="list"]').click();
    mocks.map.focusChurch.mockClear();
    element<HTMLElement>('.card').click();
    expect(mocks.map.focusChurch).not.toHaveBeenCalled();
    element<HTMLButtonElement>('.view-toggle [data-view="map"]').click();
    expect(mocks.map.invalidate).toHaveBeenCalledTimes(2);
    expect(mocks.map.focusChurch).toHaveBeenLastCalledWith(expect.any(Array), {
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

  it('uses an IP estimate only for a broad map view when browser location is unavailable', async () => {
    const position = { latitude: 48.2, longitude: 16.3 };
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: async () =>
            url === 'https://ipwho.is/' ? { success: true, ...position } : database,
        }),
      ),
    );
    await start();
    await vi.waitFor(() =>
      expect(mocks.map.showApproximateLocation).toHaveBeenCalledWith(position),
    );
    expect(fetch).toHaveBeenCalledWith('https://ipwho.is/', { credentials: 'omit' });
    expect(mocks.map.setOrigin).not.toHaveBeenCalled();
    expect(mocks.map.fitToResults).not.toHaveBeenCalled();
    expect(element('#status').textContent).toBe(messages.en.geolocationUnsupported);
  });

  it('does not let a late IP response override GPS', async () => {
    let respondIp: (response: Response) => void = () => {};
    let respondGps: PositionCallback = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        url === 'https://ipwho.is/'
          ? new Promise<Response>((resolve) => {
              respondIp = resolve;
            })
          : Promise.resolve({ ok: true, json: async () => database }),
      ),
    );
    vi.stubGlobal('navigator', {
      languages: ['en'],
      geolocation: { getCurrentPosition: (success: PositionCallback) => (respondGps = success) },
    });
    await start();
    const gps = { latitude: 47, longitude: 15 };
    respondGps({ coords: gps } as GeolocationPosition);
    respondIp({
      ok: true,
      json: async () => ({ success: true, latitude: 48, longitude: 16 }),
    } as Response);
    await vi.waitFor(() => expect(mocks.map.setOrigin).toHaveBeenCalledWith(gps));
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mocks.map.showApproximateLocation).not.toHaveBeenCalled();
    expect(element('#status').textContent).toContain(messages.en.yourLocation);
  });

  it('replaces the IP view with a later GPS location', async () => {
    let respondGps: PositionCallback = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: async () =>
            url === 'https://ipwho.is/'
              ? { success: true, latitude: 48.2, longitude: 16.3 }
              : database,
        }),
      ),
    );
    vi.stubGlobal('navigator', {
      languages: ['en'],
      geolocation: { getCurrentPosition: (success: PositionCallback) => (respondGps = success) },
    });
    await start();
    await vi.waitFor(() => expect(mocks.map.showApproximateLocation).toHaveBeenCalledOnce());
    const gps = { latitude: 47, longitude: 15 };
    respondGps({ coords: gps } as GeolocationPosition);
    expect(mocks.map.setOrigin).toHaveBeenCalledWith(gps);
    expect(mocks.map.fitToResults).toHaveBeenCalled();
    expect(element('#status').textContent).toContain(messages.en.yourLocation);
  });

  it('preserves an IP view if browser location subsequently fails', async () => {
    let failGps: PositionErrorCallback = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: async () =>
            url === 'https://ipwho.is/'
              ? { success: true, latitude: 48.2, longitude: 16.3 }
              : database,
        }),
      ),
    );
    vi.stubGlobal('navigator', {
      languages: ['en'],
      geolocation: {
        getCurrentPosition: (_success: PositionCallback, failure: PositionErrorCallback) =>
          (failGps = failure),
      },
    });
    await start();
    await vi.waitFor(() => expect(mocks.map.showApproximateLocation).toHaveBeenCalledOnce());
    failGps({ code: 1 } as GeolocationPositionError);
    expect(mocks.map.fitToResults).not.toHaveBeenCalled();
    expect(element('#status').textContent).toBe(messages.en.geolocationFailed);
  });

  it('ignores a late IP estimate after the user interacts with the map', async () => {
    let respondIp: (response: Response) => void = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        url === 'https://ipwho.is/'
          ? new Promise<Response>((resolve) => {
              respondIp = resolve;
            })
          : Promise.resolve({ ok: true, json: async () => database }),
      ),
    );
    await start();
    element('#map').dispatchEvent(new Event('pointerdown'));
    respondIp({
      ok: true,
      json: async () => ({ success: true, latitude: 48, longitude: 16 }),
    } as Response);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mocks.map.showApproximateLocation).not.toHaveBeenCalled();
  });

  it('does not overwrite a manually selected pin with a late IP estimate', async () => {
    let respondIp: (response: Response) => void = () => {};
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        url === 'https://ipwho.is/'
          ? new Promise<Response>((resolve) => {
              respondIp = resolve;
            })
          : Promise.resolve({ ok: true, json: async () => database }),
      ),
    );
    await start();
    const pin = { latitude: 47, longitude: 15 };
    mocks.handlers.onPick(pin);
    respondIp({
      ok: true,
      json: async () => ({ success: true, latitude: 48, longitude: 16 }),
    } as Response);
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(mocks.map.showApproximateLocation).not.toHaveBeenCalled();
    expect(mocks.map.setOrigin).toHaveBeenLastCalledWith(pin);
  });

  it('ignores invalid IP estimates and keeps the normal map fallback', async () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {});
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve({
          ok: true,
          json: async () =>
            url === 'https://ipwho.is/'
              ? { success: true, latitude: 100, longitude: 16 }
              : database,
        }),
      ),
    );
    await start();
    await vi.waitFor(() => expect(warn).toHaveBeenCalledOnce());
    expect(mocks.map.showApproximateLocation).not.toHaveBeenCalled();
    expect(mocks.map.fitToResults).toHaveBeenCalled();
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
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        url === 'https://ipwho.is/'
          ? new Promise<Response>(() => {})
          : Promise.resolve({ ok: false, status: 500 }),
      ),
    );
    await import('./main');
    await vi.waitFor(() => expect(element('#status').textContent).toBe(messages.en.loadFailed));
    expect(mocks.map.setResults).not.toHaveBeenCalled();
  });
});
