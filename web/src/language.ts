export function displayLanguage(language: string): string {
  return language.trim().toLowerCase() === 'unknown' ? '' : language;
}
