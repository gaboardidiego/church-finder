import { describe, expect, it } from 'vitest';
import { parseDatabase } from './data';

const church = (uuid: string, extra: object = {}) => ({
  name: 'A',
  website: 'https://a.at',
  position: { latitude: 48.2, longitude: 16.3 },
  religion: 'christian',
  denomination: 'catholic',
  uuid,
  ...extra,
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
