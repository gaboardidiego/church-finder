import type { Church, Service, ServiceIndexEntry } from './types';

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === 'object' && v !== null && !Array.isArray(v);

const str = (v: unknown): string => (typeof v === 'string' ? v.trim() : '');

function parseService(raw: unknown): Service | null {
  if (!isRecord(raw)) return null;
  const date = str(raw.date);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;
  return {
    date,
    startTime: str(raw.start_time),
    language: str(raw.language) || 'Unknown',
  };
}

function parseServices(raw: unknown): Service[] {
  return (Array.isArray(raw) ? raw : [])
    .map(parseService)
    .filter((s): s is Service => s !== null)
    .sort((a, b) => a.date.localeCompare(b.date) || a.startTime.localeCompare(b.startTime));
}

function parseServiceIndex(raw: unknown): ServiceIndexEntry[] {
  if (Array.isArray(raw))
    return raw
      .map(parseService)
      .filter((s): s is Service => s !== null)
      .map(({ date, language }) => ({ date, language }));
  if (!isRecord(raw)) return [];
  const entries: ServiceIndexEntry[] = [];
  for (const [language, dates] of Object.entries(raw)) {
    if (!Array.isArray(dates)) continue;
    const name = str(language) || 'Unknown';
    for (const date of dates) {
      const value = str(date);
      if (/^\d{4}-\d{2}-\d{2}$/.test(value)) entries.push({ date: value, language: name });
    }
  }
  return entries;
}

const regions = new Set([
  'wien',
  'burgenland',
  'kaernten',
  'niederoesterreich',
  'oberoesterreich',
  'salzburg',
  'steiermark',
  'tirol',
  'vorarlberg',
]);

function scheduleFilename(
  region: string | undefined,
  files: Record<string, unknown>,
): string | null {
  if (!region || (!regions.has(region) && !/^italy-[a-z0-9-]+$/.test(region))) return null;
  const filename = files[region];
  return typeof filename === 'string' &&
    new RegExp(`^services-${region}-[a-f0-9]+\\.json$`).test(filename)
    ? filename
    : null;
}

/** Converts the raw database JSON into churches, skipping entries that cannot be used. */
export function parseDatabase(raw: unknown): Church[] {
  if (!isRecord(raw) || !Array.isArray(raw.churches)) return [];
  const servicesByChurch = isRecord(raw.services) ? raw.services : {};
  const churches: Church[] = [];
  for (const item of raw.churches) {
    if (!isRecord(item)) continue;
    const id = str(item.uuid);
    const pos = isRecord(item.position) ? item.position : {};
    const latitude = Number(pos.latitude);
    const longitude = Number(pos.longitude);
    if (!id || !Number.isFinite(latitude) || !Number.isFinite(longitude)) continue;
    const rawServices = servicesByChurch[id];
    const services = parseServices(rawServices);
    const lastVerifiedAt = str(item.last_verified_at);
    const indexed = Array.isArray(item.service_index) || isRecord(item.service_index);
    const serviceIndex = indexed ? parseServiceIndex(item.service_index) : [];
    churches.push({
      id,
      name: str(item.name) || 'Unnamed church',
      website: str(item.website),
      position: { latitude, longitude },
      religion: str(item.religion),
      denomination: str(item.denomination),
      services,
      ...(item.schedule_source === 'ember'
        ? {
            scheduleSource: 'ember' as const,
            ...(/^\d{4}-\d{2}-\d{2}$/.test(lastVerifiedAt) ? { lastVerifiedAt } : {}),
          }
        : {}),
      ...(indexed
        ? {
            region: str(item.region),
            serviceIndex,
            scheduleStatus: serviceIndex.length === 0 ? ('loaded' as const) : ('unloaded' as const),
          }
        : {}),
    });
  }

  return churches;
}

/** Shares requests by region and retains successful schedules for the lifetime of the index. */
export class ScheduleLoader {
  private requests = new Map<string, Promise<void>>();

  constructor(
    private churches: Church[],
    private indexUrl: string,
    private serviceFiles: Record<string, unknown>,
  ) {}

  load(church: Church): Promise<void> {
    const region = church.region;
    const filename = scheduleFilename(region, this.serviceFiles);
    if (!region || !filename) {
      church.scheduleStatus = 'error';
      return Promise.reject(new Error('Missing or invalid schedule file'));
    }
    const existing = this.requests.get(region);
    if (existing) return existing;
    const group = this.churches.filter((item) => item.region === region && item.serviceIndex);
    for (const item of group) item.scheduleStatus = 'loading';
    const request = fetch(new URL(filename, new URL(this.indexUrl, document.baseURI)).href)
      .then(async (response) => {
        if (!response.ok) throw new Error(`Could not load schedules (${response.status})`);
        const raw: unknown = await response.json();
        if (!isRecord(raw) || !isRecord(raw.services)) throw new Error('Invalid schedule data');
        const services = raw.services;
        const parsed = new Map<string, Service[]>();
        for (const item of group) {
          const rawServices = services[item.id];
          if (item.serviceIndex?.length && !Array.isArray(rawServices))
            throw new Error('Missing church schedules');
          const entries = parseServices(rawServices);
          if (
            item.serviceIndex?.some(
              (summary) =>
                !entries.some(
                  (service) =>
                    service.date === summary.date && service.language === summary.language,
                ),
            )
          )
            throw new Error('Incomplete church schedules');
          parsed.set(item.id, entries);
        }
        for (const item of group) {
          item.services = parsed.get(item.id) ?? [];
          item.scheduleStatus = 'loaded';
        }
      })
      .catch((error: unknown) => {
        for (const item of group) item.scheduleStatus = 'error';
        this.requests.delete(region);
        throw error;
      });
    this.requests.set(region, request);
    return request;
  }
}
export async function loadChurches(url: string): Promise<Church[]> {
  return (await loadDatabase(url)).churches;
}

export async function loadDatabase(
  url: string,
): Promise<{ churches: Church[]; serviceFiles: Record<string, unknown> }> {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Could not load data (${response.status})`);
  const raw: unknown = await response.json();
  const churches = parseDatabase(raw);
  const serviceFiles = isRecord(raw) && isRecord(raw.service_files) ? raw.service_files : {};
  for (const church of churches)
    if (church.serviceIndex && !scheduleFilename(church.region, serviceFiles))
      church.scheduleStatus = 'error';
  return {
    churches,
    serviceFiles,
  };
}

export async function loadDatabases(urls: string[]): Promise<{
  churches: Church[];
  serviceFiles: Record<string, unknown>;
  failures: { url: string; error: unknown }[];
}> {
  if (!urls.length) throw new Error('No database URLs');
  const directories = urls.map((url) => new URL('.', new URL(url, document.baseURI)).href);
  if (directories.some((directory) => directory !== directories[0]))
    throw new Error('Database files must share a directory');
  const results = await Promise.allSettled(urls.map(loadDatabase));
  const failures = results.flatMap((result, index) =>
    result.status === 'rejected' ? [{ url: urls[index]!, error: result.reason }] : [],
  );
  if (failures.length === urls.length)
    throw new AggregateError(
      failures.map(({ error }) => error),
      'Could not load any country database',
    );
  const churches: Church[] = [];
  const ids = new Set<string>();
  const serviceFiles: Record<string, unknown> = {};
  for (const result of results) {
    if (result.status === 'rejected') continue;
    const database = result.value;
    for (const church of database.churches) {
      if (ids.has(church.id)) throw new Error(`Duplicate church ID: ${church.id}`);
      ids.add(church.id);
      churches.push(church);
    }
    for (const [region, filename] of Object.entries(database.serviceFiles)) {
      if (Object.hasOwn(serviceFiles, region))
        throw new Error(`Duplicate schedule region: ${region}`);
      serviceFiles[region] = filename;
    }
  }
  return { churches, serviceFiles, failures };
}
