import { messages, type Locale, type TranslationKey } from '../i18n';

const STORAGE_KEY = 'church-finder-locale';

export function getSavedLocale(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function saveLocale(locale: Locale): void {
  try {
    localStorage.setItem(STORAGE_KEY, locale);
  } catch {
    // The chosen language still applies for this session when storage is unavailable.
  }
}

export function applyLocale(locale: Locale): void {
  const translate = (key: string | undefined): string | undefined =>
    key && Object.hasOwn(messages[locale], key)
      ? messages[locale][key as TranslationKey]
      : undefined;

  document.documentElement.lang = locale;
  for (const node of document.querySelectorAll<HTMLElement>('[data-i18n]')) {
    const text = translate(node.dataset.i18n);
    if (text !== undefined) node.textContent = text;
  }
  for (const node of document.querySelectorAll<HTMLElement>('[data-i18n-placeholder]')) {
    const text = translate(node.dataset.i18nPlaceholder);
    if (text !== undefined) node.setAttribute('placeholder', text);
  }
  for (const node of document.querySelectorAll<HTMLElement>('[data-i18n-aria-label]')) {
    const text = translate(node.dataset.i18nAriaLabel);
    if (text !== undefined) node.setAttribute('aria-label', text);
  }
  document.title = messages[locale].title;
  for (const selector of [
    'meta[name="description"]',
    'meta[property="og:description"]',
    'meta[name="twitter:description"]',
  ]) {
    document.querySelector(selector)?.setAttribute('content', messages[locale].description);
  }
  for (const selector of ['meta[property="og:title"]', 'meta[name="twitter:title"]']) {
    document.querySelector(selector)?.setAttribute('content', messages[locale].title);
  }
  document.querySelector('meta[property="og:locale"]')?.setAttribute('content', locale);
}
