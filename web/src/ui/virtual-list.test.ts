import { describe, expect, it, vi } from 'vitest';
import { messages } from '../i18n';
import type { Result } from '../types';
import { VirtualResults } from './virtual-list';

const results: Result[] = Array.from({ length: 1000 }, (_, index) => ({
  church: {
    id: String(index),
    name: `Church ${index}`,
    website: '',
    position: { latitude: 48, longitude: 16 },
    religion: '',
    denomination: '',
    services: [],
  },
  services: [],
  distanceKm: null,
}));

describe('virtual results', () => {
  it('keeps a bounded window while scrolling to the last result and updating a card', () => {
    const container = document.createElement('div');
    Object.defineProperty(container, 'clientHeight', { value: 500 });
    const onRender = vi.fn();
    const list = new VirtualResults(
      container,
      { onHover: vi.fn(), onSelect: vi.fn(), onOpenWebsite: vi.fn(), onOpenMap: vi.fn() },
      onRender,
    );
    list.setResults(results, false, 'en', messages.en);
    expect(container.querySelectorAll('.card').length).toBeLessThan(20);
    expect(container.querySelector('.card')?.getAttribute('aria-posinset')).toBe('1');

    container.scrollTop = 190 * 995;
    container.dispatchEvent(new Event('scroll'));
    expect(container.querySelectorAll('.card').length).toBeLessThan(20);
    expect(container.querySelector('.card[data-id="999"]')).not.toBeNull();
    expect(container.querySelector('.card')?.getAttribute('aria-setsize')).toBe('1000');

    const last = results[999]!;
    last.services = [{ date: '2026-10-24', startTime: '10:00', language: 'English' }];
    const card = container.querySelector('.card[data-id="999"]');
    const renders = onRender.mock.calls.length;
    list.update(last);
    expect(container.querySelector('.card[data-id="999"]')).toBe(card);
    expect(card?.textContent).toContain('10:00');
    expect(onRender).toHaveBeenCalledTimes(renders);
  });

  it('keeps keyboard focus across window changes and tabs into the next results', () => {
    const container = document.createElement('div');
    Object.defineProperty(container, 'clientHeight', { value: 500 });
    document.body.append(container);
    const list = new VirtualResults(
      container,
      { onHover: vi.fn(), onSelect: vi.fn(), onOpenWebsite: vi.fn(), onOpenMap: vi.fn() },
      vi.fn(),
    );
    list.setResults(results, false, 'en', messages.en);
    const first = container.querySelector<HTMLElement>('.card a')!;
    first.focus();
    container.scrollTop = 190;
    container.dispatchEvent(new Event('scroll'));
    expect(document.activeElement?.closest('.card')?.getAttribute('data-id')).toBe('0');

    const cards = container.querySelectorAll<HTMLElement>('.card');
    const last = cards[cards.length - 1]!;
    const lastId = Number(last.dataset.id);
    last.querySelector<HTMLElement>('a')!.focus();
    last
      .querySelector<HTMLElement>('a')!
      .dispatchEvent(new KeyboardEvent('keydown', { key: 'Tab', bubbles: true, cancelable: true }));
    expect(document.activeElement?.closest('.card')?.getAttribute('data-id')).toBe(
      String(lastId + 1),
    );
    container.remove();
  });
});
