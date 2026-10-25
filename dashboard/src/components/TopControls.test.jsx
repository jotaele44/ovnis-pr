import React from 'react'
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'

import TopControls from '@/components/TopControls'
import { setLocale, getLocale } from '@/lib/locale'
import { setThemeMode, getThemeMode, initTheme } from '@/lib/theme'

// main.jsx calls initTheme() once at startup; it is what syncs <html> to the mode.
initTheme()

beforeEach(() => {
  setLocale('en')
  setThemeMode('dark')
})

describe('TopControls', () => {
  it('labels the language buttons by flag but names them in words', () => {
    render(<TopControls />)
    const en = screen.getByRole('button', { name: 'English' })
    const es = screen.getByRole('button', { name: 'Español' })
    expect(en).toHaveTextContent('🇺🇸')
    expect(es).toHaveTextContent('🇵🇷')
    expect(es).toHaveAttribute('lang', 'es')
    expect(en).toHaveAttribute('aria-pressed', 'true')
    expect(es).toHaveAttribute('aria-pressed', 'false')
  })

  it('switches language, the <html lang>, and the control labels', async () => {
    const user = userEvent.setup()
    render(<TopControls />)
    await user.click(screen.getByRole('button', { name: 'Español' }))
    expect(getLocale()).toBe('es')
    expect(document.documentElement.lang).toBe('es')
    expect(screen.getByRole('button', { name: 'Español' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /Tema: oscuro/ })).toBeInTheDocument()
  })

  it('cycles the theme and announces the current mode', async () => {
    const user = userEvent.setup()
    render(<TopControls />)
    await user.click(screen.getByRole('button', { name: /Theme: dark/ }))
    expect(getThemeMode()).toBe('light')
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(screen.getByRole('button', { name: /Theme: light/ })).toBeInTheDocument()
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = render(<TopControls />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
