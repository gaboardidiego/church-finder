import type { Result } from '../types';
import { renderResults, type ListHandlers } from './list';
import type { Locale, Messages } from '../i18n';

const ESTIMATED_HEIGHT = 190;
const OVERSCAN = 4;

export class VirtualResults {
  private results: Result[] = [];
  private heights = new Map<string, number>();
  private start = -1;
  private end = -1;
  private showDates = false;
  private locale: Locale = 'en';
  private text!: Messages;

  constructor(
    private container: HTMLElement,
    private handlers: ListHandlers,
    private onRender: () => void,
  ) {
    container.addEventListener('scroll', () => this.render());
    container.addEventListener('keydown', (event) => this.onKeydown(event));
    window.addEventListener('resize', () => this.render());
  }

  setResults(results: Result[], showDates: boolean, locale: Locale, text: Messages): void {
    this.results = results;
    this.showDates = showDates;
    this.locale = locale;
    this.text = text;
    this.start = -1;
    this.container.scrollTop = 0;
    this.render();
  }

  show(id: string): void {
    const index = this.results.findIndex((result) => result.church.id === id);
    if (index < 0) return;
    if (index < this.start || index >= this.end) {
      this.container.scrollTop = this.offset(index);
      this.render();
    }
    const card = [...this.container.querySelectorAll<HTMLElement>('.card')].find(
      (item) => item.dataset.id === id,
    );
    card?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  update(result: Result): void {
    const card = [...this.container.querySelectorAll<HTMLElement>('.card')].find(
      (item) => item.dataset.id === result.church.id,
    );
    if (!card) return;
    const temporary = document.createElement('div');
    renderResults(temporary, [result], this.showDates, this.handlers, this.locale, this.text);
    const replacement = temporary.firstElementChild;
    if (replacement) card.replaceChildren(...replacement.childNodes);
    this.measure();
  }

  render(): void {
    if (!this.text) return;
    if (!this.results.length) {
      if (this.start !== 0 || this.end !== 0) {
        this.start = this.end = 0;
        renderResults(this.container, [], this.showDates, this.handlers, this.locale, this.text);
        this.onRender();
      }
      return;
    }
    const top = this.container.scrollTop;
    const bottom = top + (this.container.clientHeight || 800);
    let offset = 0;
    let first = 0;
    while (first < this.results.length && offset + this.height(first) < top) {
      offset += this.height(first++);
    }
    let last = first;
    while (last < this.results.length && offset < bottom) offset += this.height(last++);
    const start = Math.max(0, first - OVERSCAN);
    const end = Math.min(this.results.length, last + OVERSCAN);
    if (start === this.start && end === this.end) return;
    const active = document.activeElement;
    const activeCard = active instanceof HTMLElement ? active.closest<HTMLElement>('.card') : null;
    const activeId = activeCard?.dataset.id;
    const activeIndex =
      activeCard && active instanceof HTMLElement
        ? [...activeCard.querySelectorAll('a, button')].indexOf(active)
        : -1;
    this.start = start;
    this.end = end;
    const temporary = document.createElement('div');
    renderResults(
      temporary,
      this.results.slice(start, end),
      this.showDates,
      this.handlers,
      this.locale,
      this.text,
    );
    const before = document.createElement('div');
    const after = document.createElement('div');
    before.className = 'list-spacer';
    after.className = 'list-spacer';
    before.setAttribute('aria-hidden', 'true');
    after.setAttribute('aria-hidden', 'true');
    for (const [index, card] of [...temporary.children].entries()) {
      card.setAttribute('aria-posinset', String(start + index + 1));
      card.setAttribute('aria-setsize', String(this.results.length));
    }
    this.container.replaceChildren(before, ...temporary.childNodes, after);
    this.measure();
    this.onRender();
    if (activeId && activeIndex >= 0) {
      const card = [...this.container.querySelectorAll<HTMLElement>('.card')].find(
        (item) => item.dataset.id === activeId,
      );
      card?.querySelectorAll<HTMLElement>('a, button')[activeIndex]?.focus({ preventScroll: true });
    }
  }

  private onKeydown(event: KeyboardEvent): void {
    if (event.key !== 'Tab' || !(event.target instanceof HTMLElement)) return;
    const card = event.target.closest<HTMLElement>('.card');
    if (!card) return;
    const controls = [...card.querySelectorAll<HTMLElement>('a, button')];
    const backwards = event.shiftKey;
    const boundary = backwards ? controls[0] : controls.at(-1);
    const current = backwards ? this.results[this.start] : this.results[this.end - 1];
    const nextIndex = backwards ? this.start - 1 : this.end;
    const next = this.results[nextIndex];
    if (event.target !== boundary || card.dataset.id !== current?.church.id || !next) return;
    event.preventDefault();
    this.container.scrollTop = this.offset(nextIndex);
    this.render();
    const nextCard = [...this.container.querySelectorAll<HTMLElement>('.card')].find(
      (item) => item.dataset.id === next.church.id,
    );
    const nextControls = nextCard?.querySelectorAll<HTMLElement>('a, button');
    const control = backwards ? nextControls?.[nextControls.length - 1] : nextControls?.[0];
    control?.focus();
  }

  private height(index: number): number {
    const result = this.results[index];
    return result ? (this.heights.get(result.church.id) ?? ESTIMATED_HEIGHT) : ESTIMATED_HEIGHT;
  }

  private offset(end: number): number {
    let total = 0;
    for (let index = 0; index < end; index++) total += this.height(index);
    return total;
  }

  private measure(): void {
    for (const card of this.container.querySelectorAll<HTMLElement>('.card')) {
      const height = card.getBoundingClientRect().height;
      if (card.dataset.id && height > 0) this.heights.set(card.dataset.id, height + 12);
    }
    const spacers = this.container.querySelectorAll<HTMLElement>('.list-spacer');
    if (spacers[0]) spacers[0].style.height = `${this.offset(this.start)}px`;
    if (spacers[1])
      spacers[1].style.height = `${this.offset(this.results.length) - this.offset(this.end)}px`;
  }
}
