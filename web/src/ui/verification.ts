import { formatMessage, messages, type Locale } from '../i18n';
import type { Church } from '../types';

export function verificationLabel(church: Church, locale: Locale): string {
  if (church.scheduleSource !== 'ember') return '';
  return church.lastVerifiedAt
    ? formatMessage(locale, 'scheduleVerified', { date: church.lastVerifiedAt })
    : messages[locale].verificationUnknown;
}
