import React from 'react'
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'

import MobileNav, { PRIMARY_VIEWS, MORE_VIEWS } from '@/components/MobileNav'
import { setLocale } from '@/lib/locale'

beforeEach(() => setLocale('en'))

describe('MobileNav', () => {
  it('keeps the persistent bar to five destinations including More (spec cap)', () => {
    expect(PRIMARY_VIEWS.length + 1).toBeLessThanOrEqual(5)
    render(<MobileNav view="cases" onChange={() => {}} />)
    const nav = screen.getByRole('navigation', { name: 'OVNIS mobile navigation' })
    expect(nav.querySelectorAll('button')).toHaveLength(PRIMARY_VIEWS.length + 1)
  })

  it('marks the current view and reports a tap', async () => {
    const user = userEvent.setup()
    const seen = []
    render(<MobileNav view="cases" onChange={(v) => seen.push(v)} />)
    expect(screen.getByRole('button', { name: 'Cases' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Map' })).not.toHaveAttribute('aria-current')
    await user.click(screen.getByRole('button', { name: 'Statistics' }))
    expect(seen).toEqual(['stats'])
  })

  it('opens the More sheet, navigates from it and closes it', async () => {
    const user = userEvent.setup()
    const seen = []
    render(<MobileNav view="cases" onChange={(v) => seen.push(v)} status="470 cases · 469 mapped" />)
    await user.click(screen.getByRole('button', { name: 'More' }))
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(screen.getByText('470 cases · 469 mapped')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Activity' }))
    expect(seen).toEqual([MORE_VIEWS[0].id])
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('highlights More while a view that lives inside it is active', () => {
    render(<MobileNav view="activity" onChange={() => {}} />)
    expect(screen.getByRole('button', { name: 'More' })).toHaveAttribute('aria-current', 'page')
  })

  it('has no detectable accessibility violations', async () => {
    const { container } = render(<MobileNav view="cases" onChange={() => {}} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
