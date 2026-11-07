import { initAnalytics, trackEvent } from './analytics';
import { loadChurches } from './data';
import { formatMessage, isLocale, messages, resolveLocale } from './i18n';
import { ALL_DENOMINATIONS, ALL_LANGUAGES, dateForDay, filterResults, toIsoDate } from './filters';
import type { Church, Filters, Position } from './types';
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
  originLabel: 'yourPin' | 'yourLocation' | '';
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

const map = new ChurchMap($('#map'), {
  onPick: (position) => {
    trackEvent('pin_location');
    pickPosition(position);
  },
  onSelect: (id) => setActiveCard(resultsEl, id, true),
});

function pickPosition(position: Position): void {
  setOrigin(position, 'yourPin');
}

function setStatus(message: string): void {
  statusEl.textContent = message;
}

function setOrigin(position: Position | null, label: 'yourPin' | 'yourLocation', fit = true): void {
  state.origin = position;
  state.originLabel = position ? label : '';
  map.setOrigin(position);
  setStatus(
    position ? formatMessage(locale, 'sortedByDistance', { label: messages[locale][label] }) : '',
  );
  refresh(fit);
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
  renderResults(
    resultsEl,
    results,
    filters.date === null || state.weekend,
    {
      onHover: (id) => map.highlight(id),
      onSelect: (id) => {
        map.highlight(id, true);
        setActiveCard(resultsEl, id, false);
      },
      onOpenWebsite: () => trackEvent('open_website'),
      onOpenMap: () => trackEvent('open_google_maps'),
    },
    locale,
    messages[locale],
  );
  map.setResults(results);
  if (fit) map.fitToResults(results);
  if (!state.origin)
    setStatus(
      formatMessage(locale, results.length === 1 ? 'oneChurch' : 'noChurches', {
        count: results.length,
      }),
    );
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
  if (state.origin)
    setStatus(
      formatMessage(locale, 'sortedByDistance', {
        label: state.originLabel ? messages[locale][state.originLabel] : '',
      }),
    );
  refresh(false);
});
nameInput.addEventListener('input', () => {
  state.filters.query = nameInput.value;
  refresh();
});
nameInput.addEventListener('change', () => trackEvent('search_name'));

$('#locate').addEventListener('click', () => {
  trackEvent('use_location');
  if (!navigator.geolocation) {
    setStatus(messages[locale].geolocationUnsupported);
    return;
  }
  setStatus(messages[locale].locating);
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => {
      const position = { latitude: coords.latitude, longitude: coords.longitude };
      setOrigin(position, 'yourLocation', false);
      map.panTo(position);
    },
    () => setStatus(messages[locale].geolocationFailed),
    { enableHighAccuracy: false, timeout: 10000 },
  );
});

document.querySelectorAll<HTMLElement>('.view-toggle button').forEach((button) =>
  button.addEventListener('click', () => {
    layoutEl.dataset.view = button.dataset.view ?? 'list';
    document
      .querySelectorAll('.view-toggle button')
      .forEach((b) => b.classList.toggle('active', b === button));
    map.invalidate();
  }),
);

async function start(): Promise<void> {
  initAnalytics();
  applyLocale(locale);
  uiLanguageSelect.value = locale;
  dateInput.value = state.filters.date ?? '';
  updateChips('today');
  try {
    state.churches = await loadChurches(
      `${import.meta.env.BASE_URL}data/churches_vienna.database.json`,
    );
  } catch {
    setStatus(messages[locale].loadFailed);
    return;
  }
  populateFilters();
  refresh();
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
