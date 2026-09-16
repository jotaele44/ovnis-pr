import { describe, expect, it, vi } from 'vitest'

vi.mock('maplibre-gl', () => ({ default: {} }))

import { parseCaseDensity } from './CaseMap'

describe('case density contract', () => {
  it('validates arithmetic and identity scope', () => {
    const result = parseCaseDensity({
      by_geoid: { 72999: 2 },
      matched_count: 2,
      unmatched: 1,
      total_cases: 3,
      scope: { identity_effect: 'NONE', state: 'CANDIDATE_NOT_IDENTITY' },
    })

    expect(result.byGeoid).toEqual({ 72999: 2 })
    expect(result.matchedCount + result.unmatchedCount).toBe(result.totalCases)
  })

  it('rejects a successful response whose arithmetic does not close', () => {
    expect(() => parseCaseDensity({
      by_geoid: { 72999: 2 },
      matched_count: 2,
      unmatched: 0,
      total_cases: 3,
      scope: { identity_effect: 'NONE' },
    })).toThrow('arithmetic does not close')
  })
})
