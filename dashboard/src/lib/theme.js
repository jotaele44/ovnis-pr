import { useCallback } from 'react'
import { createPref } from '@/lib/prefs'

// dark is the app's identity, so it is the default; `system` follows the OS.
export const THEME_MODES = ['dark', 'light', 'system']

const META_COLOR = { dark: '#8a148c', light: '#f8fafc' }

const pref = createPref('ovnis.theme', 'dark', (v) => THEME_MODES.includes(v))

const prefersDark = () =>
  typeof window.matchMedia !== 'function' || window.matchMedia('(prefers-color-scheme: dark)').matches

export const resolveTheme = (mode, systemDark = prefersDark()) =>
  mode === 'system' ? (systemDark ? 'dark' : 'light') : mode

export const nextThemeMode = (mode) => THEME_MODES[(THEME_MODES.indexOf(mode) + 1) % THEME_MODES.length]

// Stamps the signals federation.css and Tailwind's `dark` variant read.
export function applyTheme(mode = pref.get()) {
  const resolved = resolveTheme(mode)
  const root = document.documentElement
  root.dataset.theme = resolved
  root.classList.toggle('dark', resolved === 'dark')
  root.style.colorScheme = resolved
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', META_COLOR[resolved])
  return resolved
}

let started = false

// Called once at startup: applies the stored mode and keeps `system` live.
// Idempotent, so a second call (HMR, a test) cannot stack listeners.
export function initTheme() {
  applyTheme()
  if (started) return
  started = true
  pref.subscribe(() => applyTheme())
  if (typeof window.matchMedia === 'function') {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (pref.get() === 'system') applyTheme()
    })
  }
}

export const setThemeMode = (mode) => pref.set(mode)
export const getThemeMode = () => pref.get()

export function useTheme() {
  const mode = pref.use()
  const cycle = useCallback(() => pref.set(nextThemeMode(pref.get())), [])
  return { mode, resolved: resolveTheme(mode), setMode: pref.set, cycle }
}
