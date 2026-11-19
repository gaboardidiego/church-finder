import { describe, expect, it } from 'vitest';
import { displayLanguage } from './language';

describe('service languages', () => {
  it.each([
    ['en', 'English'],
    [' ENGLIS ', 'English'],
    ['english', 'English'],
    ['ar', 'Arabic'],
    ['bi', 'Bislama'],
    ['hr', 'Croatian'],
    ['ta', 'Tamil'],
    ['zh', 'Chinese'],
    ['Unknown', ''],
    [' unrecognized ', 'unrecognized'],
  ])('displays %s as %s', (value, expected) => {
    expect(displayLanguage(value)).toBe(expected);
  });
});
