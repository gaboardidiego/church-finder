import { formatDistance } from '../geo';
import { formatMessage, type Locale, type Messages } from '../i18n';
import type { Position, Result, Service } from '../types';

const el = <K extends keyof HTMLElementTagNameMap>(
  tag: K,
  className?: string,
  text?: string,
): HTMLElementTagNameMap[K] => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
};

export const humanize = (value: string): string =>
  value.replace(/[_;]/g, (c) => (c === '_' ? ' ' : ', '));

function formatServiceDate(iso: string, locale: Locale): string {
  const [y = 0, m = 1, d = 1] = iso.split('-').map(Number);
  const dateLocale = locale === 'de' ? 'de-AT' : locale === 'it' ? 'it-IT' : 'en-GB';
  return new Date(y, m - 1, d).toLocaleDateString(dateLocale, {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
}

export function serviceLabel(service: Service, showDate: boolean, locale: Locale): string {
  const parts = [
    showDate ? formatServiceDate(service.date, locale) : '',
    service.startTime,
    service.language,
  ];
  return parts.filter(Boolean).join(' · ');
}

export interface ListHandlers {
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  onOpenWebsite: (id: string) => void;
  onOpenMap: (id: string) => void;
}

const svg = (paths: string): string =>
  `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
const GLOBE_ICON = svg(
  '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/>',
);
const PIN_ICON = svg(
  '<path d="M12 21s-7-5.6-7-11a7 7 0 0 1 14 0c0 5.4-7 11-7 11z"/><circle cx="12" cy="10" r="2.5"/>',
);

export const googleMapsUrl = ({ latitude, longitude }: Position): string =>
  `https://www.google.com/maps/search/?api=1&query=${latitude}%2C${longitude}`;

export function renderResults(
  container: HTMLElement,
  results: Result[],
  showDates: boolean,
  handlers: ListHandlers,
  locale: Locale,
  text: Messages,
): void {
  container.replaceChildren();
  if (results.length === 0) {
    container.append(el('p', 'empty', text.noServices));
    return;
  }
  for (const { church, services, distanceKm } of results) {
    const card = el('article', 'card');
    card.dataset.id = church.id;
    card.addEventListener('mouseenter', () => handlers.onHover(church.id));
    card.addEventListener('mouseleave', () => handlers.onHover(null));
    card.addEventListener('click', () => handlers.onSelect(church.id));

    const head = el('div', 'card-head');
    head.append(el('h2', undefined, church.name));
    if (distanceKm !== null) head.append(el('span', 'distance', formatDistance(distanceKm)));
    card.append(head);

    const meta = [church.denomination, church.religion].find(Boolean);
    if (meta) card.append(el('p', 'meta', humanize(meta)));

    const chips = el('div', 'service-list');
    if (services.length === 0) {
      chips.append(el('span', 'muted', text.noServicesListed));
    } else {
      for (const s of services.slice(0, 6))
        chips.append(el('span', 'chip', serviceLabel(s, showDates, locale)));
      if (services.length > 6)
        chips.append(
          el('span', 'muted', formatMessage(locale, 'more', { count: services.length - 6 })),
        );
    }
    card.append(chips);

    const actions = el('div', 'actions');
    const addLink = (
      label: string,
      icon: string,
      href: string,
      onClick: () => void,
      primary = false,
    ): void => {
      const link = el('a', primary ? 'action primary' : 'action');
      link.insertAdjacentHTML('beforeend', icon);
      link.append(el('span', undefined, label));
      link.href = href;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.addEventListener('click', (e) => {
        e.stopPropagation();
        onClick();
      });
      actions.append(link);
    };
    if (/^https?:\/\//i.test(church.website))
      addLink(
        text.website,
        GLOBE_ICON,
        church.website,
        () => handlers.onOpenWebsite(church.id),
        true,
      );
    addLink(text.directions, PIN_ICON, googleMapsUrl(church.position), () =>
      handlers.onOpenMap(church.id),
    );
    card.append(actions);
    container.append(card);
  }
}

export function setActiveCard(container: HTMLElement, id: string | null, scroll: boolean): void {
  for (const card of container.querySelectorAll<HTMLElement>('.card')) {
    const active = card.dataset.id === id;
    card.classList.toggle('active', active);
    if (active && scroll) card.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }
}
