import { afterEach, describe, expect, it, vi } from 'vitest';
import { searchPlace } from './nominatim';

afterEach(() => vi.unstubAllGlobals());

const stubFetch = (body: unknown, ok = true) =>
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok, status: ok ? 200 : 500, json: async () => body }),
  );

describe('searchPlace', () => {
  it('returns null for empty input without calling the network', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    expect(await searchPlace('  ')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('parses the first result', async () => {
    stubFetch([{ lat: '48.2', lon: '16.3', display_name: 'Somewhere' }]);
    expect(await searchPlace('x')).toEqual({
      label: 'Somewhere',
      position: { latitude: 48.2, longitude: 16.3 },
    });
  });

  it('returns null when nothing is found and throws on HTTP errors', async () => {
    stubFetch([]);
    expect(await searchPlace('x')).toBeNull();
    stubFetch([], false);
    await expect(searchPlace('x')).rejects.toThrow();
  });
});
