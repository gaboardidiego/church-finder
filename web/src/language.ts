const languages: Record<string, string[]> = {
  Arabic: ['ar'],
  Bislama: ['bi'],
  'Church Slavonic': ['cu'],
  Chinese: ['zh'],
  Croatian: ['hr'],
  English: ['en', 'eng', 'englis'],
  Filipino: ['fil'],
  French: ['fr'],
  German: ['de'],
  Italian: ['it'],
  Latin: ['la'],
  Lithuanian: ['lt'],
  Malayalam: ['ml'],
  Polish: ['pl'],
  Portuguese: ['pt'],
  Slovak: ['sk'],
  Spanish: ['es'],
  Tamil: ['ta'],
  Vietnamese: ['vi'],
};

const languageNames = new Map(
  Object.entries(languages).flatMap(([name, aliases]) =>
    [name.toLowerCase(), ...aliases].map((alias) => [alias, name] as const),
  ),
);

export function displayLanguage(language: string): string {
  const trimmed = language.trim();
  const key = trimmed.toLowerCase();
  if (key === 'unknown') return '';
  return languageNames.get(key) ?? trimmed;
}
