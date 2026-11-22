import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import * as maplibregl from 'maplibre-gl'

// A browser without WebGL makes the MapLibre constructor throw. The Map view
// must say so, and leaving it must not throw (the app's only error boundary
// wraps the navigation too).
vi.mock('maplibre-gl', () => ({
  setWorkerUrl: vi.fn(),
  Map: vi.fn().mockImplementation(function MapWithoutWebGL() {
    throw new Error('Failed to initialize WebGL.')
  }),
  NavigationControl: vi.fn(),
  Popup: vi.fn(),
}))
vi.mock('maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url', () => ({ default: 'worker.js' }))

import CaseMap from './CaseMap'

const EMPTY = { type: 'FeatureCollection', features: [] }

describe('CaseMap without WebGL', () => {
  it('registers the bundled worker so the map does not fetch index.html as its worker', () => {
    expect(maplibregl.setWorkerUrl).toHaveBeenCalledWith('worker.js')
  })

  it('shows why the map is unavailable and unmounts cleanly', () => {
    const { unmount } = render(<CaseMap geojson={EMPTY} onSelect={() => {}} />)
    expect(screen.getByRole('status').textContent).toContain('Map unavailable: Failed to initialize WebGL.')
    expect(() => unmount()).not.toThrow()
  })
})
