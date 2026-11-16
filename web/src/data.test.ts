import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadDatabase, parseDatabase, ScheduleLoader } from './data';

afterEach(() => vi.unstubAllGlobals());

const church = (uuid: string, extra: object = {}) => ({
  name: 'A',
  website: 'https://a.at',
  position: { latitude: 48.2, longitude: 16.3 },
  religion: 'christian',
  denomination: 'catholic',
  uuid,
  ...extra,
});

describe('regional schedules', () => {
  const index = {
    churches: [
      church('1', { region: 'wien', service_index: [{ date: '2026-10-24', language: 'German' }] }),
      church('2', { region: 'wien', service_index: [{ date: '2026-10-24', language: 'English' }] }),
    ],
    services: {},
    service_files: { wien: 'services-wien-abcd1234.json' },
  };
  const schedules = {
    services: {
      '1': [{ date: '2026-10-24', start_time: '10:00', language: 'German' }],
      '2': [{ date: '2026-10-24', start_time: '11:00', language: 'English' }],
    },
  };

  it('deduplicates concurrent and completed requests and resolves relative to the index', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => schedules });
    vi.stubGlobal('fetch', fetch);
    const churches = parseDatabase(index);
    const loader = new ScheduleLoader(churches, '/app/data/index.json', index.service_files);
    const first = loader.load(churches[0]!);
    const second = loader.load(churches[1]!);
    expect(first).toBe(second);
    expect(churches[1]?.scheduleStatus).toBe('loading');
    await first;
    await loader.load(churches[0]!);
    expect(fetch).toHaveBeenCalledOnce();
    expect(fetch.mock.calls[0]?.[0]).toBe(
      new URL('/app/data/services-wien-abcd1234.json', document.baseURI).href,
    );
    expect(churches[1]?.services[0]?.startTime).toBe('11:00');
  });

  it('reports missing mappings and incomplete data, and allows retry after failure', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, json: async () => index })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ services: {} }) })
      .mockResolvedValueOnce({ ok: true, json: async () => schedules });
    vi.stubGlobal('fetch', fetch);
    const { churches, serviceFiles } = await loadDatabase('/data/index.json');
    const loader = new ScheduleLoader(churches, '/data/index.json', serviceFiles);
    await expect(loader.load(churches[0]!)).rejects.toThrow('Missing church schedules');
    expect(churches[1]?.scheduleStatus).toBe('error');
    await loader.load(churches[0]!);
    expect(churches[1]?.scheduleStatus).toBe('loaded');

    fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ ...index, service_files: {} }),
    });
    const invalid = await loadDatabase('/data/index.json');
    expect(invalid.churches[0]?.scheduleStatus).toBe('error');
    await expect(
      new ScheduleLoader(invalid.churches, '/data/index.json', invalid.serviceFiles).load(
        invalid.churches[0]!,
      ),
    ).rejects.toThrow('Missing or invalid');
  });
});

describe('parseDatabase', () => {
  it('joins services to churches and sorts them', () => {
    const result = parseDatabase({
      churches: [church('1')],
      services: {
        '1': [
          { language: 'German', start_time: '10:00', date: '2026-10-25' },
          { language: 'English', start_time: '09:00', date: '2026-10-24' },
        ],
      },
    });
    expect(result[0]?.services.map((s) => s.date)).toEqual(['2026-10-24', '2026-10-25']);
    expect(result[0]?.services[0]?.startTime).toBe('09:00');
  });

  it('is robust against missing or malformed data', () => {
    expect(parseDatabase(null)).toEqual([]);
    expect(parseDatabase({})).toEqual([]);
    const result = parseDatabase({
      churches: [
        church('1', { name: '', website: undefined }),
        church('2', { position: {} }),
        'junk',
        church('', {}),
      ],
      services: { '1': [{ date: 'bad' }, null, { date: '2026-10-24' }] },
    });
    expect(result).toHaveLength(1);
    expect(result[0]?.name).toBe('Unnamed church');
    expect(result[0]?.website).toBe('');
    expect(result[0]?.services).toEqual([
      { date: '2026-10-24', startTime: '', language: 'Unknown' },
    ]);
  });
});
