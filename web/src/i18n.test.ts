import { describe, expect, it } from 'vitest';
import { formatMessage, resolveLocale } from './i18n';

describe('locale selection', () => {
  it('prefers a saved supported locale', () => {
    expect(resolveLocale(['de-AT', 'it-IT'], 'it')).toBe('it');
  });

  it('uses the first supported browser language', () => {
    expect(resolveLocale(['fr-FR', 'de-AT', 'it-IT'])).toBe('de');
  });

  it('falls back to English for unsupported languages', () => {
    expect(resolveLocale(['fr-FR', 'es-ES'])).toBe('en');
  });

  it('formats localized messages', () => {
    expect(formatMessage('de', 'sortedByDistance', { label: 'deinem Pin' })).toBe(
      'Sortiert nach Entfernung von: deinem Pin',
    );
  });
});
