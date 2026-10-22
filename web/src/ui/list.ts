import { formatDistance } from '../geo';
import type { Result, Service } from '../types';

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

const humanize = (value: string): string => value.replace(/_/g, ' ');

function formatServiceDate(iso: string): string {
  const [y = 0, m = 1, d = 1] = iso.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  });
}

export function serviceLabel(service: Service, showDate: boolean): string {
  const parts = [
    showDate ? formatServiceDate(service.date) : '',
    service.startTime,
    service.language,
  ];
  return parts.filter(Boolean).join(' · ');
}

export interface ListHandlers {
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  onOpenWebsite: (id: string) => void;
}

export function renderResults(
  container: HTMLElement,
  results: Result[],
  showDates: boolean,
  handlers: ListHandlers,
): void {
  container.replaceChildren();
  if (results.length === 0) {
    container.append(el('p', 'empty', 'No services found. Try another day or language.'));
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
      chips.append(el('span', 'muted', 'No services listed'));
    } else {
      for (const s of services.slice(0, 6))
        chips.append(el('span', 'chip', serviceLabel(s, showDates)));
      if (services.length > 6) chips.append(el('span', 'muted', `+${services.length - 6} more`));
    }
    card.append(chips);

    if (/^https?:\/\//i.test(church.website)) {
      const link = el('a', 'website', 'Website ↗');
      link.href = church.website;
      link.target = '_blank';
      link.rel = 'noopener noreferrer';
      link.addEventListener('click', (e) => {
        e.stopPropagation();
        handlers.onOpenWebsite(church.id);
      });
      card.append(link);
    }
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
