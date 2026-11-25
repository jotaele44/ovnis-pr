import { useCallback, useEffect } from 'react'
import { createPref } from '@/lib/prefs'

export const LOCALES = ['en', 'es']
// Flags are the visible label; aria-labels carry the language name.
export const LOCALE_FLAG = { en: '🇺🇸', es: '🇵🇷' }
export const LOCALE_NAME = { en: 'English', es: 'Español' }

// Interpolation is `{name}`. A key missing from `es` falls back to English,
// then to the key itself, so an untranslated string is visible, not blank.
export const MESSAGES = {
  en: {
    'app.subtitle': 'Puerto Rico UAP sighting registry & witness review',
    'health.unreachable': 'backend unreachable',
    'health.connecting': 'connecting…',
    'health.summary': '{master} cases · {mapped} mapped · {unmapped} unmapped',
    'map.legend': '{count} mapped sightings · colored by evidence tier',
    'nav.label': 'OVNIS mobile navigation',
    'nav.cases': 'Cases',
    'nav.map': 'Map',
    'nav.stats': 'Statistics',
    'nav.candidates': 'Candidates',
    'nav.activity': 'Activity',
    'nav.more': 'More',
    'nav.moreDescription': 'Other views and backend status',
    'ctl.theme': 'Theme: {mode}. Tap to change.',
    'ctl.language': 'Language',
    'theme.dark': 'dark',
    'theme.light': 'light',
    'theme.system': 'system',
    'cases.search.label': 'Search cases',
    'cases.search.placeholder': 'Search by case, place, agency or year…',
    'cases.period': 'Period',
    'cases.tier': 'Tier',
    'cases.allPeriods': 'All periods',
    'cases.allTiers': 'All tiers',
    'cases.ofTotal': 'of {total} cases',
    'cases.list': 'Cases',
    'cases.empty.title': 'No cases found',
    'cases.empty.description': 'No case matches the current search and filters.',
    'cases.reset': 'Reset search',
    'cases.removeFilter': 'Remove filter: {label}',
    'cases.perPage': 'Per page',
    'cases.pagination': 'Case pages',
    'cases.pageOf': 'Page {page} of {pages}',
    'cases.prev': 'Previous page',
    'cases.next': 'Next page',
    'cases.col.case': 'Case',
    'cases.col.date': 'Date',
    'cases.col.location': 'Location',
    'cases.col.agency': 'Agency',
    'cases.col.tier': 'Tier',
    'cases.noUrl': 'No URL',
    'cases.noUrlTitle': 'source has no URL',
    'cases.noCoords': 'no coordinates',
    'detail.noCoords': '(no coordinates)',
    'detail.witness': 'Witness',
    'detail.evidenceType': 'Evidence type',
    'detail.source': 'Source',
    'detail.agency': 'Agency involvement',
    'detail.gaps': 'Contradictions / gaps',
    'detail.provenance': 'Provenance',
    'detail.from': 'from',
  },
  es: {
    'app.subtitle': 'Registro de avistamientos UAP de Puerto Rico y revisión de testigos',
    'health.unreachable': 'servidor no disponible',
    'health.connecting': 'conectando…',
    'health.summary': '{master} casos · {mapped} en el mapa · {unmapped} sin ubicar',
    'map.legend': '{count} avistamientos en el mapa · coloreados por nivel de evidencia',
    'nav.label': 'Navegación móvil de OVNIS',
    'nav.cases': 'Casos',
    'nav.map': 'Mapa',
    'nav.stats': 'Estadísticas',
    'nav.candidates': 'Candidatos',
    'nav.activity': 'Actividad',
    'nav.more': 'Más',
    'nav.moreDescription': 'Otras vistas y estado del servidor',
    'ctl.theme': 'Tema: {mode}. Toca para cambiar.',
    'ctl.language': 'Idioma',
    'theme.dark': 'oscuro',
    'theme.light': 'claro',
    'theme.system': 'sistema',
    'cases.search.label': 'Buscar casos',
    'cases.search.placeholder': 'Buscar por caso, lugar, agencia o año…',
    'cases.period': 'Período',
    'cases.tier': 'Nivel',
    'cases.allPeriods': 'Todos los períodos',
    'cases.allTiers': 'Todos los niveles',
    'cases.ofTotal': 'de {total} casos',
    'cases.list': 'Casos',
    'cases.empty.title': 'No se encontraron casos',
    'cases.empty.description': 'Ningún caso coincide con la búsqueda y los filtros actuales.',
    'cases.reset': 'Restablecer búsqueda',
    'cases.removeFilter': 'Quitar filtro: {label}',
    'cases.perPage': 'Por página',
    'cases.pagination': 'Páginas de casos',
    'cases.pageOf': 'Página {page} de {pages}',
    'cases.prev': 'Página anterior',
    'cases.next': 'Página siguiente',
    'cases.col.case': 'Caso',
    'cases.col.date': 'Fecha',
    'cases.col.location': 'Lugar',
    'cases.col.agency': 'Agencia',
    'cases.col.tier': 'Nivel',
    'cases.noUrl': 'Sin URL',
    'cases.noUrlTitle': 'la fuente no tiene URL',
    'cases.noCoords': 'sin coordenadas',
    'detail.noCoords': '(sin coordenadas)',
    'detail.witness': 'Testigo',
    'detail.evidenceType': 'Tipo de evidencia',
    'detail.source': 'Fuente',
    'detail.agency': 'Agencia involucrada',
    'detail.gaps': 'Contradicciones / vacíos',
    'detail.provenance': 'Procedencia',
    'detail.from': 'de',
  },
}

export const isLocale = (v) => LOCALES.includes(v)

export function translate(locale, key, vars) {
  const text = MESSAGES[locale]?.[key] ?? MESSAGES.en[key] ?? key
  return vars ? text.replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? '')) : text
}

const deviceLocale = () =>
  typeof navigator !== 'undefined' && /^es\b/i.test(navigator.language || '') ? 'es' : 'en'

const pref = createPref('ovnis.locale', deviceLocale, isLocale)

export const setLocale = (locale) => pref.set(locale)
export const getLocale = () => pref.get()

export function useLocale() {
  const locale = pref.use()
  useEffect(() => {
    document.documentElement.lang = locale
  }, [locale])
  const t = useCallback((key, vars) => translate(locale, key, vars), [locale])
  return { locale, setLocale: pref.set, t }
}
