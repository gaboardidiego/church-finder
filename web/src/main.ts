import { initAnalytics, trackEvent } from './analytics';
import { loadChurches } from './data';
import {
  ALL_DENOMINATIONS,
  ALL_LANGUAGES,
  addDays,
  applyFilters,
  collectDenominations,
  collectLanguages,
  toIsoDate,
  weekendDates,
} from './filters';
import type { Church, Filters, Position } from './types';
import { humanize, renderResults, setActiveCard } from './ui/list';
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
const statusEl = $<HTMLElement>('#status');
const resultsEl = $<HTMLElement>('#results');
const layoutEl = $<HTMLElement>('.layout');

const state: { churches: Church[]; filters: Filters; origin: Position | null; weekend: boolean } = {
  churches: [],
  filters: {
    query: '',
    date: toIsoDate(new Date()),
    language: ALL_LANGUAGES,
    denomination: ALL_DENOMINATIONS,
  },
  origin: null,
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
  setOrigin(position, 'your pin');
}

function setStatus(message: string): void {
  statusEl.textContent = message;
}

function setOrigin(position: Position | null, label: string): void {
  state.origin = position;
  map.setOrigin(position);
  setStatus(position ? `Sorted by distance from: ${label}` : '');
  refresh();
}

function refresh(fit = true): void {
  const { filters } = state;
  const base = applyFilters(
    state.churches,
    { ...filters, date: state.weekend ? null : filters.date },
    state.origin,
  );
  const weekendDays = state.weekend ? weekendDates(toIsoDate(new Date())) : null;
  const results = weekendDays
    ? base
        .map((r) => ({ ...r, services: r.services.filter((s) => weekendDays.includes(s.date)) }))
        .filter((r) => r.services.length > 0)
    : base;
  renderResults(resultsEl, results, filters.date === null || state.weekend, {
    onHover: (id) => map.highlight(id),
    onSelect: (id) => {
      map.highlight(id, true);
      setActiveCard(resultsEl, id, false);
    },
    onOpenWebsite: () => trackEvent('open_website'),
  });
  map.setResults(results);
  if (fit) map.fitToResults(results);
  if (!state.origin) setStatus(`${results.length} churches`);
}

function updateChips(active: string): void {
  for (const chip of document.querySelectorAll<HTMLElement>('#day-chips button')) {
    chip.classList.toggle('active', chip.dataset.day === active);
  }
}

function setDay(day: string): void {
  const today = toIsoDate(new Date());
  state.weekend = day === 'weekend';
  state.filters.date =
    day === 'today'
      ? today
      : day === 'tomorrow'
        ? addDays(today, 1)
        : day === 'any' || state.weekend
          ? null
          : day;
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
nameInput.addEventListener('input', () => {
  state.filters.query = nameInput.value;
  refresh();
});
nameInput.addEventListener('change', () => trackEvent('search_name'));

$('#locate').addEventListener('click', () => {
  trackEvent('use_location');
  if (!navigator.geolocation) {
    setStatus('Geolocation is not supported by your browser.');
    return;
  }
  setStatus('Locating…');
  navigator.geolocation.getCurrentPosition(
    ({ coords }) => pickPosition({ latitude: coords.latitude, longitude: coords.longitude }),
    () => setStatus('Could not get your location. Click the map to drop a pin instead.'),
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
  dateInput.value = state.filters.date ?? '';
  updateChips('today');
  try {
    state.churches = await loadChurches(
      `${import.meta.env.BASE_URL}data/churches_vienna.database.json`,
    );
  } catch {
    setStatus('Could not load church data.');
    return;
  }
  languageSelect.append(new Option('All languages', ALL_LANGUAGES));
  for (const language of collectLanguages(state.churches))
    languageSelect.append(new Option(language, language));
  denominationSelect.append(new Option('All denominations', ALL_DENOMINATIONS));
  for (const d of collectDenominations(state.churches))
    denominationSelect.append(new Option(humanize(d), d));
  refresh();
}

void start();
