import { describe, it, expect, beforeEach } from 'vitest'
import { MESSAGES, LOCALES, LOCALE_FLAG, translate, setLocale, getLocale } from '@/lib/locale'

describe('locale — string table', () => {
  it('every English key has a Spanish translation, and vice versa', () => {
    // A key missing from `es` silently falls back to English at runtime; this
    // makes a half-translated release fail here instead of in front of a user.
    const en = Object.keys(MESSAGES.en).sort()
    const es = Object.keys(MESSAGES.es).sort()
    expect(es).toEqual(en)
  })

  it('keeps the same {placeholders} in both languages', () => {
    const slots = (s) => (s.match(/\{\w+\}/g) || []).sort().join(',')
    for (const key of Object.keys(MESSAGES.en)) {
      expect(slots(MESSAGES.es[key]), key).toBe(slots(MESSAGES.en[key]))
    }
  })

  it('labels ES with the Puerto Rico flag and EN with the US flag', () => {
    expect(LOCALES).toEqual(['en', 'es'])
    expect(LOCALE_FLAG).toEqual({ en: '🇺🇸', es: '🇵🇷' })
  })
})

describe('translate', () => {
  it('interpolates variables', () => {
    expect(translate('en', 'cases.ofTotal', { total: 470 })).toBe('of 470 cases')
    expect(translate('es', 'cases.ofTotal', { total: 470 })).toBe('de 470 casos')
  })

  it('falls back to English, then to the key, so a gap is visible not blank', () => {
    expect(translate('es', 'no.such.key')).toBe('no.such.key')
    expect(translate('fr', 'cases.reset')).toBe('Reset search')
  })
})

describe('locale preference', () => {
  beforeEach(() => setLocale('en'))

  it('persists the choice and ignores unsupported locales', () => {
    setLocale('es')
    expect(getLocale()).toBe('es')
    expect(window.localStorage.getItem('ovnis.locale')).toBe('es')
    setLocale('xx')
    expect(getLocale()).toBe('es')
  })
})
