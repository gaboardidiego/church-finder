import { afterEach, describe, expect, it, vi } from 'vitest';
import { messages } from '../i18n';
import { applyLocale, getSavedLocale, saveLocale } from './locale';

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('locale UI', () => {
  it('updates translated content and metadata without replacing unknown keys', () => {
    document.head.innerHTML = `
      <meta name="description"><meta property="og:title"><meta property="og:description">
      <meta name="twitter:title"><meta name="twitter:description"><meta property="og:locale">
    `;
    document.body.innerHTML = `
      <p data-i18n="today"></p><p data-i18n="notAKey">unchanged</p>
      <input data-i18n-placeholder="churchName" data-i18n-aria-label="day">
    `;
    applyLocale('it');
    expect(document.documentElement.lang).toBe('it');
    expect(document.title).toBe(messages.it.title);
    expect(document.querySelector('[data-i18n="today"]')?.textContent).toBe(messages.it.today);
    expect(document.querySelector('[data-i18n="notAKey"]')?.textContent).toBe('unchanged');
    expect(document.querySelector('input')?.placeholder).toBe(messages.it.churchName);
    expect(document.querySelector('input')?.getAttribute('aria-label')).toBe(messages.it.day);
    expect(document.querySelector('meta[name="description"]')?.getAttribute('content')).toBe(
      messages.it.description,
    );
    expect(document.querySelector('meta[property="og:title"]')?.getAttribute('content')).toBe(
      messages.it.title,
    );
    expect(
      document.querySelector('meta[name="twitter:description"]')?.getAttribute('content'),
    ).toBe(messages.it.description);
  });

  it('keeps locale selection usable if browser storage is unavailable', () => {
    saveLocale('de');
    expect(getSavedLocale()).toBe('de');
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('storage unavailable');
    });
    expect(getSavedLocale()).toBeNull();
    expect(() => saveLocale('it')).not.toThrow();
  });
});
