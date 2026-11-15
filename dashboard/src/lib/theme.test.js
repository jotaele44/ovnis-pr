import { describe, it, expect, beforeEach } from 'vitest'
import { THEME_MODES, resolveTheme, nextThemeMode, applyTheme, setThemeMode, getThemeMode } from '@/lib/theme'

describe('theme', () => {
  beforeEach(() => setThemeMode('dark'))

  it('cycles dark → light → system → dark', () => {
    expect(THEME_MODES).toEqual(['dark', 'light', 'system'])
    expect(nextThemeMode('dark')).toBe('light')
    expect(nextThemeMode('light')).toBe('system')
    expect(nextThemeMode('system')).toBe('dark')
  })

  it('resolves system from the OS preference and leaves explicit modes alone', () => {
    expect(resolveTheme('system', true)).toBe('dark')
    expect(resolveTheme('system', false)).toBe('light')
    expect(resolveTheme('light', true)).toBe('light')
  })

  it('stamps data-theme, the .dark class and color-scheme on <html>', () => {
    applyTheme('light')
    const root = document.documentElement
    expect(root.dataset.theme).toBe('light')
    expect(root.classList.contains('dark')).toBe(false)
    expect(root.style.colorScheme).toBe('light')
    applyTheme('dark')
    expect(root.dataset.theme).toBe('dark')
    expect(root.classList.contains('dark')).toBe(true)
  })

  it('persists the mode and rejects unknown values', () => {
    setThemeMode('light')
    expect(window.localStorage.getItem('ovnis.theme')).toBe('light')
    setThemeMode('sepia')
    expect(getThemeMode()).toBe('light')
  })
})
