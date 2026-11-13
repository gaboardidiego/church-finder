import { describe, expect, it, vi } from 'vitest';
import { messages } from '../i18n';
import type { Result } from '../types';
import { googleMapsUrl, renderResults, serviceLabel, setActiveCard } from './list';

const result: Result = {
  church: {
    id: 'one',
    name: '<img src=x onerror=alert(1)>',
    website: 'https://example.org',
    position: { latitude: 48.2, longitude: 16.3 },
    religion: 'christian',
    denomination: 'roman_catholic',
    services: [],
  },
  services: Array.from({ length: 7 }, (_, index) => ({
    date: '2026-10-24',
    startTime: `0${index}:00`,
    language: 'English',
  })),
  distanceKm: 1.2,
};

function setup(results: Result[] = [result]) {
  const container = document.createElement('div');
  const handlers = {
    onHover: vi.fn(),
    onSelect: vi.fn(),
    onOpenWebsite: vi.fn(),
    onOpenMap: vi.fn(),
  };
  renderResults(container, results, false, handlers, 'en', messages.en);
  return { container, handlers };
}

describe('result cards', () => {
  it('renders safe text, services, distance and external links', () => {
    const { container } = setup();
    expect(container.querySelector('h2')?.textContent).toBe(result.church.name);
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('.meta')?.textContent).toBe('roman catholic');
    expect(container.querySelector('.distance')?.textContent).toBe('1.2 km');
    expect(container.querySelectorAll('.service-list .chip')).toHaveLength(6);
    expect(container.querySelector('.service-list .muted')?.textContent).toBe('+1 more');
    const links = container.querySelectorAll('a');
    expect(links[0]?.href).toBe('https://example.org/');
    expect(links[1]?.href).toBe(googleMapsUrl(result.church.position));
    for (const link of links) {
      expect(link.target).toBe('_blank');
      expect(link.rel).toBe('noopener noreferrer');
    }
    expect(serviceLabel(result.services[0]!, false, 'en')).toBe('00:00 · English');
    expect(serviceLabel(result.services[0]!, true, 'en')).toContain('24 Oct');
  });

  it('dispatches card and link interactions without selecting the card for a link', () => {
    const { container, handlers } = setup();
    const card = container.querySelector('article')!;
    card.dispatchEvent(new MouseEvent('mouseenter'));
    card.dispatchEvent(new MouseEvent('mouseleave'));
    card.click();
    for (const link of container.querySelectorAll('a')) {
      link.addEventListener('click', (event) => event.preventDefault());
      link.click();
    }
    expect(handlers.onHover.mock.calls).toEqual([['one'], [null]]);
    expect(handlers.onSelect).toHaveBeenCalledOnce();
    expect(handlers.onSelect).toHaveBeenCalledWith('one');
    expect(handlers.onOpenWebsite).toHaveBeenCalledWith('one');
    expect(handlers.onOpenMap).toHaveBeenCalledWith('one');
    setActiveCard(container, 'one', false);
    expect(card.classList.contains('active')).toBe(true);
    setActiveCard(container, null, false);
    expect(card.classList.contains('active')).toBe(false);
  });

  it('omits unknown languages without hiding service times or dates', () => {
    const unknown = { date: '2026-10-24', startTime: '10:00', language: 'Unknown' };
    expect(serviceLabel(unknown, false, 'en')).toBe('10:00');
    expect(serviceLabel(unknown, true, 'en')).toContain('24 Oct · 10:00');
    expect(serviceLabel({ ...unknown, startTime: '' }, false, 'en')).toBe('');
    const rendered = setup([
      { ...result, services: [unknown, { ...unknown, startTime: '', language: 'unknown' }] },
    ]).container;
    expect(rendered.querySelectorAll('.chip')).toHaveLength(1);
    expect(rendered.querySelector('.chip')?.textContent).toBe('10:00');
  });

  it('handles empty results, missing services and unsafe website URLs', () => {
    const { container } = setup([]);
    expect(container.textContent).toBe(messages.en.noServices);
    const noServices = {
      ...result,
      church: { ...result.church, website: 'javascript:alert(1)' },
      services: [],
      distanceKm: null,
    };
    const rendered = setup([noServices]).container;
    expect(rendered.querySelector('.service-list')?.textContent).toBe(messages.en.noServicesListed);
    expect(rendered.querySelectorAll('a')).toHaveLength(1);
    expect(rendered.querySelector('.distance')).toBeNull();
  });
});
