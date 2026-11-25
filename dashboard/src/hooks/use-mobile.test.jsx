import React from 'react'
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { useIsMobile, MOBILE_BREAKPOINT } from '@/hooks/use-mobile'

const original = window.matchMedia
export const setViewportMatches = (matches) => {
  window.matchMedia = (media) => ({
    matches, media, addEventListener() {}, removeEventListener() {},
  })
}
afterEach(() => { window.matchMedia = original })

function Probe() {
  return <p>{useIsMobile() ? 'mobile' : 'desktop'}</p>
}

describe('useIsMobile', () => {
  it('uses the spec breakpoint of 860px', () => {
    expect(MOBILE_BREAKPOINT).toBe(860)
  })

  it('reports mobile on the very first render, with no desktop flash', () => {
    setViewportMatches(true)
    // renderToString-style check: read the initial render before effects run.
    const seen = []
    function Spy() {
      seen.push(useIsMobile())
      return null
    }
    render(<Spy />)
    expect(seen[0]).toBe(true)
  })

  it('reports desktop when the media query does not match', () => {
    setViewportMatches(false)
    render(<Probe />)
    expect(screen.getByText('desktop')).toBeInTheDocument()
  })
})
