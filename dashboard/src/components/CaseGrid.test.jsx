import React from 'react'
import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { axe } from 'vitest-axe'

import CaseGrid, { filterCases, pageSlice, searchText, DEFAULT_PAGE_SIZE } from '@/components/CaseGrid'
import { setLocale } from '@/lib/locale'

const original = window.matchMedia
const setMobile = (matches) => {
  window.matchMedia = (media) => ({ matches, media, addEventListener() {}, removeEventListener() {} })
}

const mk = (i, over = {}) => ({
  case_id: `PR-${String(i).padStart(4, '0')}`,
  date_raw: `${1950 + (i % 60)}`,
  decade: `${1950 + Math.floor((i % 60) / 10) * 10}s`,
  evidence_tier: ['T1', 'T2', 'T3', 'T4'][i % 4],
  description: `Light over the coast number ${i}`,
  location: { string: i % 2 ? 'Aguadilla, PR' : 'Lajas, PR', lat: 18, lon: -67 },
  source_url: 'https://example.gov/doc',
  source_family: i === 3 ? 'FBI' : 'none',
  ...over,
})
const CASES = Array.from({ length: 30 }, (_, i) => mk(i + 1))

beforeEach(() => setLocale('en'))
afterEach(() => { window.matchMedia = original })

describe('filterCases — what the search box matches', () => {
  it('finds a case by its id, its year and its agency, not just the description', () => {
    expect(filterCases(CASES, { q: 'pr-0007' })).toHaveLength(1)
    expect(filterCases(CASES, { q: '1957' }).map((c) => c.case_id)).toContain('PR-0007')
    expect(filterCases(CASES, { q: 'fbi' }).map((c) => c.case_id)).toEqual(['PR-0003'])
  })

  it('combines text with the period and tier filters', () => {
    const rows = filterCases(CASES, { q: 'lajas', tier: 'T3' })
    expect(rows.length).toBeGreaterThan(0)
    expect(rows.every((c) => c.evidence_tier === 'T3' && searchText(c).includes('lajas'))).toBe(true)
  })

  it('treats a whitespace-only query as no query', () => {
    expect(filterCases(CASES, { q: '   ' })).toHaveLength(CASES.length)
  })
})

describe('pageSlice', () => {
  it('clamps an out-of-range page instead of returning an empty page', () => {
    const { current, pageCount, items } = pageSlice(CASES, 99, 12)
    expect(pageCount).toBe(3)
    expect(current).toBe(2)
    expect(items).toHaveLength(6)
  })

  it('always has at least one page, even with no rows', () => {
    expect(pageSlice([], 0, 12)).toMatchObject({ current: 0, pageCount: 1, items: [] })
  })
})

describe('CaseGrid — desktop table', () => {
  beforeEach(() => setMobile(false))

  it('shows one page of rows and the real total', async () => {
    render(<CaseGrid cases={CASES} />)
    expect(screen.getByTestId('case-count')).toHaveTextContent(String(CASES.length))
    expect(screen.getByRole('table')).toBeInTheDocument()
    expect(screen.getAllByRole('row')).toHaveLength(DEFAULT_PAGE_SIZE + 1) // + header
    expect(screen.getByText('Page 1 of 3')).toBeInTheDocument()
  })

  it('pages forward and back, disabling the ends', async () => {
    const user = userEvent.setup()
    render(<CaseGrid cases={CASES} />)
    const prev = screen.getByRole('button', { name: 'Previous page' })
    const next = screen.getByRole('button', { name: 'Next page' })
    expect(prev).toBeDisabled()
    await user.click(next)
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
    await user.click(next)
    expect(next).toBeDisabled()
    await user.click(prev)
    expect(screen.getByText('Page 2 of 3')).toBeInTheDocument()
  })

  it('returns to page 1 when the search changes', async () => {
    const user = userEvent.setup()
    render(<CaseGrid cases={CASES} />)
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    await user.type(screen.getByRole('searchbox'), 'Aguadilla')
    expect(screen.getByText(/Page 1 of 2/)).toBeInTheDocument()
  })

  it('shows an empty state with a Reset search button that restores everything', async () => {
    const user = userEvent.setup()
    render(<CaseGrid cases={CASES} />)
    await user.type(screen.getByRole('searchbox'), 'zzz-nothing-matches')
    expect(screen.getByTestId('case-count')).toHaveTextContent('0')
    expect(screen.getByText('No cases found')).toBeInTheDocument()
    // No pagination for zero rows.
    expect(screen.queryByRole('button', { name: 'Next page' })).not.toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Reset search' }))
    expect(screen.getByTestId('case-count')).toHaveTextContent(String(CASES.length))
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.queryByText('No cases found')).not.toBeInTheDocument()
  })

  it('offers a removable chip for an active search', async () => {
    const user = userEvent.setup()
    render(<CaseGrid cases={CASES} />)
    await user.type(screen.getByRole('searchbox'), 'lajas')
    await user.click(screen.getByRole('button', { name: /Remove filter/ }))
    expect(screen.getByRole('searchbox')).toHaveValue('')
    expect(screen.getByTestId('case-count')).toHaveTextContent(String(CASES.length))
  })

  it('calls onSelect with the full case when a row is clicked', async () => {
    const user = userEvent.setup()
    const seen = []
    render(<CaseGrid cases={CASES} onSelect={(c) => seen.push(c.case_id)} />)
    await user.click(screen.getByText('PR-0002'))
    expect(seen).toEqual(['PR-0002'])
  })
})

describe('CaseGrid — mobile cards', () => {
  beforeEach(() => setMobile(true))

  it('renders touch cards, not a table, with labelled filter fields', () => {
    render(<CaseGrid cases={CASES} />)
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
    const list = screen.getByRole('list', { name: 'Cases' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(DEFAULT_PAGE_SIZE)
    expect(screen.getByText('Period')).toBeInTheDocument()
    expect(screen.getAllByText('Tier').length).toBeGreaterThan(0)
  })

  it('selects a case from a card, marking it pressed', async () => {
    const user = userEvent.setup()
    const seen = []
    const { rerender } = render(<CaseGrid cases={CASES} onSelect={(c) => seen.push(c.case_id)} />)
    await user.click(screen.getByRole('button', { name: /PR-0001/ }))
    expect(seen).toEqual(['PR-0001'])
    rerender(<CaseGrid cases={CASES} selectedId="PR-0001" onSelect={() => {}} />)
    expect(screen.getByRole('button', { name: /PR-0001/ })).toHaveAttribute('aria-pressed', 'true')
  })

  it('flags a source with no URL on the card', () => {
    render(<CaseGrid cases={[mk(1, { source_url: 'El Mundo, p. 3' })]} />)
    expect(screen.getByText('No URL')).toBeInTheDocument()
  })

  it('speaks Spanish when the locale is es', () => {
    setLocale('es')
    render(<CaseGrid cases={CASES} />)
    expect(screen.getByText(/de 30 casos/)).toBeInTheDocument()
    expect(screen.getByText('Período')).toBeInTheDocument()
    expect(screen.getByText('Página 1 de 3')).toBeInTheDocument()
  })

  it('has no detectable accessibility violations (list + empty state)', async () => {
    const { container, rerender } = render(<CaseGrid cases={CASES} />)
    expect(await axe(container)).toHaveNoViolations()
    rerender(<CaseGrid cases={[]} />)
    expect(await axe(container)).toHaveNoViolations()
  })
})
