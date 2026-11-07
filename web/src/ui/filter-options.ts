import {
  ALL_DENOMINATIONS,
  ALL_LANGUAGES,
  collectDenominations,
  collectLanguages,
} from '../filters';
import type { Messages } from '../i18n';
import type { Church, Filters } from '../types';
import { humanize } from './list';

export function populateFilterOptions(
  languageSelect: HTMLSelectElement,
  denominationSelect: HTMLSelectElement,
  churches: Church[],
  filters: Filters,
  text: Messages,
): void {
  languageSelect.replaceChildren(new Option(text.allLanguages, ALL_LANGUAGES));
  for (const language of collectLanguages(churches))
    languageSelect.append(new Option(language, language));
  denominationSelect.replaceChildren(new Option(text.allDenominations, ALL_DENOMINATIONS));
  for (const denomination of collectDenominations(churches))
    denominationSelect.append(new Option(humanize(denomination), denomination));
  languageSelect.value = filters.language;
  denominationSelect.value = filters.denomination;
}
