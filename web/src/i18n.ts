export const locales = ['en', 'de', 'it'] as const;
export type Locale = (typeof locales)[number];

export const messages = {
  en: {
    scopeAlert: 'Church-service listings from across Austria are shown.',
    churchName: 'Church name…',
    useLocation: '◎ Use my location',
    today: 'Today',
    tomorrow: 'Tomorrow',
    weekend: 'This weekend',
    anyDay: 'Any day',
    day: 'Day',
    serviceLanguage: 'Service language',
    denomination: 'Denomination',
    displayLanguage: 'Display language',
    hint: '💡 Click anywhere on the map to drop a pin — churches are sorted by distance from it.',
    list: 'List',
    map: 'Map',
    results: 'Results',
    mapLabel: 'Map',
    sortedByDistance: 'Sorted by distance from: {label}',
    yourPin: 'your pin',
    yourLocation: 'your location',
    geolocationUnsupported: 'Geolocation is not supported by your browser.',
    locating: 'Locating…',
    geolocationFailed: 'Could not get your location. Click the map to drop a pin instead.',
    loadFailed: 'Could not load church data.',
    allLanguages: 'All languages',
    allDenominations: 'All denominations',
    noChurches: '{count} churches',
    oneChurch: '{count} church',
    noServices: 'No services found. Try another day or language.',
    noServicesListed: 'No services listed',
    more: '+{count} more',
    moreChurches: '+{count} churches',
    website: 'Website',
    directions: 'Directions',
    title: 'Church Finder Austria – Church Services, Mass Times & Liturgies',
    description:
      'Find church services across Austria by day, language and location, with times and map.',
  },
  de: {
    scopeAlert: 'Gottesdienste aus ganz Österreich werden angezeigt.',
    churchName: 'Kirchenname…',
    useLocation: '◎ Meinen Standort verwenden',
    today: 'Heute',
    tomorrow: 'Morgen',
    weekend: 'Dieses Wochenende',
    anyDay: 'Beliebiger Tag',
    day: 'Tag',
    serviceLanguage: 'Gottesdienstsprache',
    denomination: 'Konfession',
    displayLanguage: 'Anzeigesprache',
    hint: '💡 Klicke auf die Karte, um einen Pin zu setzen — Kirchen werden nach Entfernung sortiert.',
    list: 'Liste',
    map: 'Karte',
    results: 'Ergebnisse',
    mapLabel: 'Karte',
    sortedByDistance: 'Sortiert nach Entfernung von: {label}',
    yourPin: 'deinem Pin',
    yourLocation: 'deinem Standort',
    geolocationUnsupported: 'Dein Browser unterstützt keine Standortbestimmung.',
    locating: 'Standort wird ermittelt…',
    geolocationFailed:
      'Standort konnte nicht ermittelt werden. Klicke stattdessen auf die Karte, um einen Pin zu setzen.',
    loadFailed: 'Kirchendaten konnten nicht geladen werden.',
    allLanguages: 'Alle Sprachen',
    allDenominations: 'Alle Konfessionen',
    noChurches: '{count} Kirchen',
    oneChurch: '{count} Kirche',
    noServices:
      'Keine Gottesdienste gefunden. Versuche einen anderen Tag oder eine andere Sprache.',
    noServicesListed: 'Keine Gottesdienste angegeben',
    more: '+{count} weitere',
    moreChurches: '+{count} Kirchen',
    website: 'Website',
    directions: 'Route',
    title: 'Church Finder Österreich – Gottesdienste, Messen & Liturgien',
    description:
      'Finde Gottesdienste in ganz Österreich nach Tag, Sprache und Standort, mit Uhrzeiten und Karte.',
  },
  it: {
    scopeAlert: 'Sono mostrati gli orari delle funzioni religiose in tutta l’Austria.',
    churchName: 'Nome della chiesa…',
    useLocation: '◎ Usa la mia posizione',
    today: 'Oggi',
    tomorrow: 'Domani',
    weekend: 'Questo fine settimana',
    anyDay: 'Qualsiasi giorno',
    day: 'Giorno',
    serviceLanguage: 'Lingua della celebrazione',
    denomination: 'Confessione',
    displayLanguage: 'Lingua dell’interfaccia',
    hint: '💡 Fai clic sulla mappa per aggiungere un segnaposto — le chiese saranno ordinate per distanza.',
    list: 'Elenco',
    map: 'Mappa',
    results: 'Risultati',
    mapLabel: 'Mappa',
    sortedByDistance: 'Ordinate per distanza da: {label}',
    yourPin: 'il segnaposto',
    yourLocation: 'la tua posizione',
    geolocationUnsupported: 'Il browser non supporta la geolocalizzazione.',
    locating: 'Ricerca della posizione…',
    geolocationFailed:
      'Impossibile trovare la posizione. Fai clic sulla mappa per aggiungere un segnaposto.',
    loadFailed: 'Impossibile caricare i dati delle chiese.',
    allLanguages: 'Tutte le lingue',
    allDenominations: 'Tutte le confessioni',
    noChurches: '{count} chiese',
    oneChurch: '{count} chiesa',
    noServices: 'Nessuna celebrazione trovata. Prova un altro giorno o un’altra lingua.',
    noServicesListed: 'Orari non disponibili',
    more: '+{count} altri',
    moreChurches: '+{count} chiese',
    website: 'Sito web',
    directions: 'Indicazioni',
    title: 'Church Finder Austria – Celebrazioni, messe e liturgie',
    description:
      'Trova le celebrazioni in tutta l’Austria per giorno, lingua e posizione, con orari e mappa.',
  },
} as const;

export type TranslationKey = keyof (typeof messages)['en'];
export type Messages = { readonly [Key in TranslationKey]: string };

export function resolveLocale(languages: readonly string[], savedLocale?: string | null): Locale {
  if (isLocale(savedLocale)) return savedLocale;
  for (const language of languages) {
    const locale = language.split('-')[0]?.toLowerCase();
    if (isLocale(locale)) return locale;
  }
  return 'en';
}

export function isLocale(value: string | null | undefined): value is Locale {
  return locales.includes(value as Locale);
}

export function formatMessage(
  locale: Locale,
  key: TranslationKey,
  values: Record<string, string | number> = {},
): string {
  return messages[locale][key].replace(/\{(\w+)\}/g, (_, name: string) =>
    String(values[name] ?? ''),
  );
}
