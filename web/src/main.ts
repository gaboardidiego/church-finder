import { initAnalytics, trackEvent } from './analytics';
import { loadChurches } from './data';
import { formatMessage, isLocale, messages, resolveLocale } from './i18n';
import { ALL_DENOMINATIONS, ALL_LANGUAGES, dateForDay, filterResults, toIsoDate } from './filters';
import type { Church, Filters, Position, Result } from './types';
import { populateFilterOptions } from './ui/filter-options';
import { renderResults, setActiveCard } from './ui/list';
import { applyLocale, getSavedLocale, saveLocale } from './ui/locale';
import { ChurchMap } from './ui/map';
import './style.css';

const $ = <T extends HTMLElement>(selector: string): T => {
  const node = document.querySelector<T>(selector);
  if (!node) throw new Error(`Missing element ${selector}`);
  return node;
};

const nameInput = $<HTMLInputElement>('#name-search');
const dateInput = $<HTMLInputElement>('#date');
const languageSelect = $<HTMLSelectElement>('#language');
const denominationSelect = $<HTMLSelectElement>('#denomination');
const uiLanguageSelect = $<HTMLSelectElement>('#ui-language');
const statusEl = $<HTMLElement>('#status');
const resultsEl = $<HTMLElement>('#results');
const layoutEl = $<HTMLElement>('.layout');

let locale = resolveLocale(navigator.languages, getSavedLocale());

const state: {
  churches: Church[];
  filters: Filters;
  origin: Position | null;
  originLabel: 'yourPin' | 'yourLocation' | 'yourApproximateLocation' | '';
  weekend: boolean;
} = {
  churches: [],
  filters: {
    query: '',
    date: toIsoDate(new Date()),
    language: ALL_LANGUAGES,
    denomination: ALL_DENOMINATIONS,
  },
  origin: null,
  originLabel: '',
  weekend: false,
};

let dataLoaded = false;
let dataLoadFailed = false;
let locationRequest = 0;
let locationStatus: 'locating' | 'geolocationUnsupported' | 'geolocationFailed' | null = null;
let pendingChurchFocus: string | null = null;
let pendingResultsFit = false;
let currentResults: Result[] = [];

const map = new ChurchMap($('#map'), {
  onPick: (position) => {
    trackEvent('pin_location');
    locationRequest++;
    pickPosition(position);
  },
  onSelect: (id) => {
    focusChurch(id);
    setActiveCard(resultsEl, id, true);
  },
});

function pickPosition(position: Position): void {
  setOrigin(position, 'yourPin');
}

function focusChurch(id: string): void {
  const church = state.churches.find((item) => item.id === id);
  if (!church) throw new Error(`Unknown church ${id}`);
  const results = filterResults(
    state.churches,
    state.filters,
    church.position,
    state.weekend,
    toIsoDate(new Date()),
  );
  if (locationStatus === 'locating') {
    locationRequest++;
    locationStatus = null;
    updateStatus(results.length);
  }
  if (layoutEl.dataset.view === 'list') pendingChurchFocus = id;
  else {
    pendingChurchFocus = null;
    pendingResultsFit = false;
    map.fitToResults(results, church.position);
  }
}

function setStatus(message: string): void {
  statusEl.textContent = message;
}

function updateStatus(count: number): void {
  if (dataLoadFailed) setStatus(messages[locale].loadFailed);
  else if (locationStatus) setStatus(messages[locale][locationStatus]);
  else if (state.origin && state.originLabel)
    setStatus(
      formatMessage(locale, 'sortedByDistance', { label: messages[locale][state.originLabel] }),
    );
  else setStatus(formatMessage(locale, count === 1 ? 'oneChurch' : 'noChurches', { count }));
}

function setOrigin(
  position: Position | null,
  label: 'yourPin' | 'yourLocation' | 'yourApproximateLocation',
  fit = true,
): void {
  state.origin = position;
  state.originLabel = position ? label : '';
  locationStatus = null;
  map.setOrigin(position);
  if (dataLoaded) refresh(fit);
  else {
    if (fit) map.fitToResults([]);
    updateStatus(0);
  }
}

function refresh(fit = true): void {
  const { filters } = state;
  const results = filterResults(
    state.churches,
    filters,
    state.origin,
    state.weekend,
    toIsoDate(new Date()),
  );
  currentResults = results;
  if (pendingChurchFocus && !results.some(({ church }) => church.id === pendingChurchFocus))
    pendingChurchFocus = null;
  renderResults(
    resultsEl,
    results,
    filters.date === null || state.weekend,
    {
      onHover: (id) => map.highlight(id),
      onSelect: (id) => {
        map.highlight(id);
        focusChurch(id);
        setActiveCard(resultsEl, id, false);
      },
      onOpenWebsite: () => trackEvent('open_website'),
      onOpenMap: () => trackEvent('open_google_maps'),
    },
    locale,
    messages[locale],
  );
  map.setResults(results);
  if (fit) {
    if (layoutEl.dataset.view === 'list') pendingResultsFit = true;
    else {
      pendingResultsFit = false;
      map.fitToResults(results);
    }
  }
  updateStatus(results.length);
}

function updateChips(active: string): void {
  for (const chip of document.querySelectorAll<HTMLElement>('#day-chips button')) {
    chip.classList.toggle('active', chip.dataset.day === active);
  }
}

function setDay(day: string): void {
  const today = toIsoDate(new Date());
  state.weekend = day === 'weekend';
  state.filters.date = dateForDay(day, today);
  dateInput.value = state.filters.date ?? '';
  updateChips(day);
  trackEvent(`filter_day_${day}`);
  refresh();
}

document
  .querySelectorAll<HTMLElement>('#day-chips button')
  .forEach((chip) => chip.addEventListener('click', () => setDay(chip.dataset.day ?? 'any')));
dateInput.addEventListener('change', () => {
  state.weekend = false;
  state.filters.date = dateInput.value || null;
  updateChips('');
  trackEvent('filter_date');
  refresh();
});
languageSelect.addEventListener('change', () => {
  state.filters.language = languageSelect.value;
  trackEvent('filter_language');
  refresh();
});
denominationSelect.addEventListener('change', () => {
  state.filters.denomination = denominationSelect.value;
  trackEvent('filter_denomination');
  refresh();
});
uiLanguageSelect.addEventListener('change', () => {
  if (!isLocale(uiLanguageSelect.value)) return;
  locale = uiLanguageSelect.value;
  applyLocale(locale);
  saveLocale(locale);
  populateFilters();
  refresh(false);
});
nameInput.addEventListener('input', () => {
  state.filters.query = nameInput.value;
  refresh();
});
nameInput.addEventListener('change', () => trackEvent('search_name'));

function locate(): void {
  const request = ++locationRequest;
  if (!navigator.geolocation) {
    locationStatus = 'geolocationUnsupported';
    updateStatus(0);
    return;
  }
  locationStatus = 'locating';
  updateStatus(0);
  const success =
    (cached: boolean): PositionCallback =>
    ({ coords }) => {
      if (request !== locationRequest) return;
      setOrigin(
        { latitude: coords.latitude, longitude: coords.longitude },
        cached || coords.accuracy > 1000 ? 'yourApproximateLocation' : 'yourLocation',
      );
    };
  const fail: PositionErrorCallback = (error) => {
    if (request !== locationRequest) return;
    if (error.code !== 1) {
      navigator.geolocation.getCurrentPosition(success(true), finishFailure, {
        enableHighAccuracy: false,
        maximumAge: 24 * 60 * 60 * 1000,
        timeout: 5000,
      });
    } else finishFailure();
  };
  const finishFailure = (): void => {
    if (request !== locationRequest) return;
    locationStatus = 'geolocationFailed';
    if (dataLoaded) refresh();
    else updateStatus(0);
  };
  navigator.geolocation.getCurrentPosition(success(false), fail, {
    enableHighAccuracy: false,
    maximumAge: 60000,
    timeout: 10000,
  });
}

$('#locate').addEventListener('click', () => {
  trackEvent('use_location');
  locate();
});

document.querySelectorAll<HTMLElement>('.view-toggle button').forEach((button) =>
  button.addEventListener('click', () => {
    layoutEl.dataset.view = button.dataset.view ?? 'list';
    document
      .querySelectorAll('.view-toggle button')
      .forEach((b) => b.classList.toggle('active', b === button));
    map.invalidate();
    if (layoutEl.dataset.view === 'map' && pendingChurchFocus) focusChurch(pendingChurchFocus);
    else if (layoutEl.dataset.view === 'map' && pendingResultsFit) {
      pendingResultsFit = false;
      map.fitToResults(currentResults);
    }
  }),
);

async function start(): Promise<void> {
  initAnalytics();
  applyLocale(locale);
  uiLanguageSelect.value = locale;
  dateInput.value = state.filters.date ?? '';
  updateChips('today');
  locate();
  try {
    state.churches = await loadChurches(
      `${import.meta.env.BASE_URL}data/churches_vienna.database.json`,
    );
  } catch {
    dataLoadFailed = true;
    updateStatus(0);
    return;
  }
  dataLoaded = true;
  populateFilters();
  refresh(locationStatus !== 'locating');
}

function populateFilters(): void {
  populateFilterOptions(
    languageSelect,
    denominationSelect,
    state.churches,
    state.filters,
    messages[locale],
  );
}

void start();
