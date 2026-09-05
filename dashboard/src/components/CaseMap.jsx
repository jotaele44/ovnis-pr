import { useEffect, useMemo, useRef, useState } from 'react'
import * as maplibregl from 'maplibre-gl'
import { useSpatialTools, SpatialToolsPanel } from './SpatialToolsPanel'
import { getMunicipiosCaseDensity } from '../lib/api'

// MapLibre map of OVNIS sighting cases. Renders the release GeoJSON directly
// (Point features colored by evidence tier). Same wrapper pattern as the
// skywatcher template — note the h-full container (not absolute inset-0), since
// maplibre-gl.css sets .maplibregl-map{position:relative} and would otherwise
// override `absolute` and collapse the height to 0.
// Resolve against the configured base so it works in the normal build
// (served from '/') and the VITE_OFFLINE single-file file:// export (base './').
const MUNICIPIOS_URL = new URL('geo/pr_municipios.geojson', document.baseURI).href

// AWS's free public elevation tile set — no API key, same free-public-tile
// precedent as the OSM raster basemap below.
const TERRAIN_DEM_URL = 'https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png'

// Municipios are added at runtime (style.load) rather than baked into this
// base style, since the case-density choropleth needs `promoteId` + feature-
// state — a plain style-JSON source can't be reconfigured that way later.
const OSM_STYLE = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://a.tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [
    { id: 'bg', type: 'background', paint: { 'background-color': '#0b1220' } },
    { id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-opacity': 0.85, 'raster-saturation': -0.3 } },
  ],
}

// Case-count choropleth for GET /municipios/case_density. Null-safe: a
// municipio with no density fetched yet (fillMode 'off') keeps the flat wash
// rather than reading as "zero cases".
const NO_DENSITY_FILL = '#101d33'
const DENSITY_FILL_COLOR = [
  'case', ['==', ['feature-state', 'case_count'], null], NO_DENSITY_FILL,
  ['step', ['feature-state', 'case_count'],
    '#1e3a5f',
    1, '#2563eb',
    10, '#818cf8',
    30, '#38bdf8',
  ],
]
const DENSITY_FILL_OPACITY = [
  'case', ['==', ['feature-state', 'case_count'], null], 0.9,
  0.7,
]

const EMPTY = { type: 'FeatureCollection', features: [] }
const PR_CENTER = [-66.4, 18.22]

const TIER_LEGEND = [
  { tier: 'T1', color: '#38bdf8', label: 'T1 · highest confidence' },
  { tier: 'T2', color: '#818cf8', label: 'T2' },
  { tier: 'T3', color: '#a78bfa', label: 'T3' },
  { tier: 'T4', color: '#64748b', label: 'T4 · lowest confidence' },
]
const TIER_COLOR = [
  'match', ['get', 'evidence_tier'],
  ...TIER_LEGEND.flatMap(({ tier, color }) => [tier, color]),
  '#64748b',
]

// date_local is zero-padded but variable-precision (YYYY, YYYY-MM, or
// YYYY-MM-DD — schemas/case_record.schema.json), so a bare string comparison
// against a full YYYY-MM-DD filter bound would wrongly exclude a year-only
// case from any range not starting exactly at that year's boundary. Expand
// each case's own precision to the widest date span it could mean before
// comparing, so imprecise dates are never silently dropped by the filter.
function dateBounds(dateLocal) {
  if (!dateLocal) return null
  if (dateLocal.length === 4) return [`${dateLocal}-01-01`, `${dateLocal}-12-31`]
  if (dateLocal.length === 7) return [`${dateLocal}-01`, `${dateLocal}-31`]
  return [dateLocal, dateLocal]
}

function caseInRange(properties, start, end) {
  if (!start && !end) return true
  const bounds = dateBounds(properties?.date_local)
  if (!bounds) return true // no date on record — an active filter shouldn't hide it
  const [lo, hi] = bounds
  if (start && hi < start) return false
  if (end && lo > end) return false
  return true
}

export default function CaseMap({ geojson, onSelect }) {
  const containerRef = useRef(null)
  const mapRef = useRef(null)
  const readyRef = useRef(false)
  const onSelectRef = useRef(onSelect)
  onSelectRef.current = onSelect
  const [showHeatmap, setShowHeatmap] = useState(false)
  const [dateStart, setDateStart] = useState('')
  const [dateEnd, setDateEnd] = useState('')
  const [showTerrain, setShowTerrain] = useState(false)
  const [densityMode, setDensityMode] = useState('off')
  const [showTools, setShowTools] = useState(false)
  const [mapReady, setMapReady] = useState(false)

  const filteredGeojson = useMemo(() => {
    if (!dateStart && !dateEnd) return geojson || EMPTY
    const features = (geojson?.features || []).filter((f) => caseInRange(f.properties, dateStart, dateEnd))
    return { type: 'FeatureCollection', features }
  }, [geojson, dateStart, dateEnd])
  const filteredRef = useRef(filteredGeojson)
  filteredRef.current = filteredGeojson

  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: PR_CENTER,
      zoom: 8.2,
    })
    mapRef.current = map
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')

    // 'style.load' instead of 'load': the latter waits for raster tiles,
    // which never resolve offline, and the data layer would never appear.
    map.on('style.load', () => {
      // promoteId lets MapLibre feature-state key off geoid directly, so the
      // density choropleth (below) needs no client-side geometry mutation.
      map.addSource('municipios', { type: 'geojson', data: MUNICIPIOS_URL, promoteId: 'geoid' })
      map.addLayer({
        id: 'municipios-fill', type: 'fill', source: 'municipios',
        paint: { 'fill-color': DENSITY_FILL_COLOR, 'fill-opacity': DENSITY_FILL_OPACITY },
      }, 'osm')
      map.addLayer({
        id: 'municipios-line', type: 'line', source: 'municipios',
        paint: { 'line-color': '#33517b', 'line-width': 0.8 },
      }, 'osm')

      map.addSource('terrain-dem', {
        type: 'raster-dem', tiles: [TERRAIN_DEM_URL], tileSize: 256, encoding: 'terrarium',
      })
      map.addLayer({
        id: 'hillshade', type: 'hillshade', source: 'terrain-dem',
        paint: { 'hillshade-exaggeration': 0.6 },
        layout: { visibility: 'none' },
      }, 'osm')

      map.addSource('cases', {
        type: 'geojson',
        data: filteredRef.current || EMPTY,
        cluster: true,
        clusterMaxZoom: 12,
        clusterRadius: 40,
      })
      // Below the point/cluster layers so a dot or cluster bubble is never
      // hidden under the glow — the heatmap is a density backdrop, not a
      // replacement view.
      map.addLayer({
        id: 'cases-heatmap', type: 'heatmap', source: 'cases',
        layout: { visibility: showHeatmap ? 'visible' : 'none' },
        paint: { 'heatmap-intensity': 1, 'heatmap-radius': 22, 'heatmap-opacity': 0.65 },
      })
      map.addLayer({
        id: 'clusters', type: 'circle', source: 'cases', filter: ['has', 'point_count'],
        paint: {
          'circle-color': ['step', ['get', 'point_count'], '#64748b', 10, '#818cf8', 30, '#38bdf8'],
          'circle-radius': ['step', ['get', 'point_count'], 12, 10, 16, 30, 20],
          'circle-opacity': 0.85,
          'circle-stroke-color': '#0b1220',
          'circle-stroke-width': 1,
        },
      })
      map.addLayer({
        id: 'cluster-count', type: 'symbol', source: 'cases', filter: ['has', 'point_count'],
        layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 11 },
        paint: { 'text-color': '#f8fafc' },
      })
      map.addLayer({
        id: 'cases-dot', type: 'circle', source: 'cases', filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-radius': 5,
          'circle-color': TIER_COLOR,
          'circle-opacity': 0.85,
          'circle-stroke-color': '#0b1220',
          'circle-stroke-width': 1,
        },
      })
      readyRef.current = true
      setMapReady(true)
      map.on('mouseenter', 'cases-dot', () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', 'cases-dot', () => (map.getCanvas().style.cursor = ''))
      map.on('click', 'cases-dot', (e) => onSelectRef.current?.(e.features[0].properties))
      map.on('mouseenter', 'clusters', () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', 'clusters', () => (map.getCanvas().style.cursor = ''))
      map.on('click', 'clusters', async (e) => {
        const features = map.queryRenderedFeatures(e.point, { layers: ['clusters'] })
        const clusterId = features[0]?.properties?.cluster_id
        if (clusterId == null) return
        const zoom = await map.getSource('cases').getClusterExpansionZoom(clusterId)
        map.easeTo({ center: features[0].geometry.coordinates, zoom })
      })
    })

    return () => { readyRef.current = false; map.remove() }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (!readyRef.current || !mapRef.current) return
    mapRef.current.getSource('cases')?.setData(filteredGeojson)
  }, [filteredGeojson])

  useEffect(() => {
    if (!readyRef.current || !mapRef.current) return
    mapRef.current.setLayoutProperty('cases-heatmap', 'visibility', showHeatmap ? 'visible' : 'none')
  }, [showHeatmap])

  useEffect(() => {
    if (!mapReady || !mapRef.current) return
    const map = mapRef.current
    map.setLayoutProperty('hillshade', 'visibility', showTerrain ? 'visible' : 'none')
    if (showTerrain) {
      map.setTerrain({ source: 'terrain-dem', exaggeration: 1.3 })
      map.easeTo({ pitch: 55, duration: 600 })
    } else {
      map.setTerrain(null)
      map.easeTo({ pitch: 0, duration: 600 })
    }
  }, [showTerrain, mapReady])

  useEffect(() => {
    if (!mapReady || !mapRef.current) return
    const map = mapRef.current
    map.setPaintProperty('municipios-fill', 'fill-color', densityMode === 'density' ? DENSITY_FILL_COLOR : NO_DENSITY_FILL)
    map.setPaintProperty('municipios-fill', 'fill-opacity', densityMode === 'density' ? DENSITY_FILL_OPACITY : 0.9)
  }, [densityMode, mapReady])

  useEffect(() => {
    if (!mapReady || !mapRef.current || densityMode !== 'density') return
    const map = mapRef.current
    let cancelled = false
    getMunicipiosCaseDensity()
      .then(({ by_geoid }) => {
        if (cancelled) return
        for (const [geoid, count] of Object.entries(by_geoid || {})) {
          map.setFeatureState({ source: 'municipios', id: geoid }, { case_count: count })
        }
      })
      .catch(() => {}) // an optional overlay failing to load isn't worth surfacing as an error
    return () => {
      cancelled = true
    }
  }, [densityMode, mapReady])

  const spatialToolTargets = useMemo(
    () => ({ Cases: () => filteredGeojson.features }),
    [filteredGeojson],
  )
  const spatialTools = useSpatialTools({ mapRef, mapReady, targets: spatialToolTargets })

  return (
    <div className="relative h-full w-full">
      <div ref={containerRef} className="h-full w-full" />

      <div className="pointer-events-none absolute left-2 top-2 rounded bg-slate-900/80 px-2.5 py-2 text-[11px] text-slate-300">
        <div className="mb-1.5 text-[10px] uppercase tracking-wide text-slate-500">Evidence tier</div>
        {TIER_LEGEND.map(({ tier, color, label }) => (
          <div key={tier} className="mb-0.5 flex items-center gap-1.5 last:mb-0">
            <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color }} />
            {label}
          </div>
        ))}
        {densityMode === 'density' && (
          <>
            <div className="mb-1.5 mt-2 border-t border-slate-800 pt-2 text-[10px] uppercase tracking-wide text-slate-500">Case density</div>
            {[
              { label: '30+', color: '#38bdf8' },
              { label: '10–29', color: '#818cf8' },
              { label: '1–9', color: '#2563eb' },
              { label: '0', color: '#1e3a5f' },
            ].map(({ label, color }) => (
              <div key={label} className="mb-0.5 flex items-center gap-1.5 last:mb-0">
                <span className="inline-block h-2 w-2 shrink-0 rounded-sm" style={{ background: color }} />
                {label}
              </div>
            ))}
          </>
        )}
      </div>

      <div className="absolute right-2 top-2 flex flex-col items-end gap-1.5">
        <div className="flex gap-1.5">
          <button
            type="button"
            aria-pressed={showHeatmap}
            onClick={() => setShowHeatmap((v) => !v)}
            className={`rounded border px-2 py-1 text-[11px] transition ${showHeatmap ? 'border-sky-500/40 bg-sky-500/10 text-sky-300' : 'border-slate-800 bg-slate-900/80 text-slate-400 hover:text-slate-200'}`}
          >
            Heatmap
          </button>
          <button
            type="button"
            aria-pressed={showTerrain}
            onClick={() => setShowTerrain((v) => !v)}
            className={`rounded border px-2 py-1 text-[11px] transition ${showTerrain ? 'border-teal-500/40 bg-teal-500/10 text-teal-300' : 'border-slate-800 bg-slate-900/80 text-slate-400 hover:text-slate-200'}`}
          >
            Terrain
          </button>
          <button
            type="button"
            aria-pressed={densityMode === 'density'}
            onClick={() => setDensityMode((m) => (m === 'density' ? 'off' : 'density'))}
            className={`rounded border px-2 py-1 text-[11px] transition ${densityMode === 'density' ? 'border-blue-500/40 bg-blue-500/10 text-blue-300' : 'border-slate-800 bg-slate-900/80 text-slate-400 hover:text-slate-200'}`}
          >
            Density
          </button>
          <button
            type="button"
            aria-pressed={showTools}
            onClick={() => setShowTools((v) => !v)}
            className={`rounded border px-2 py-1 text-[11px] transition ${showTools ? 'border-pink-500/40 bg-pink-500/10 text-pink-300' : 'border-slate-800 bg-slate-900/80 text-slate-400 hover:text-slate-200'}`}
          >
            Spatial tools
          </button>
        </div>
        <div className="flex items-center gap-1 rounded border border-slate-800 bg-slate-900/80 px-2 py-1 text-[11px] text-slate-400">
          <input
            type="date"
            value={dateStart}
            onChange={(e) => setDateStart(e.target.value)}
            className="w-[110px] bg-transparent text-slate-300 [color-scheme:dark]"
            aria-label="Filter cases from date"
          />
          <span>–</span>
          <input
            type="date"
            value={dateEnd}
            onChange={(e) => setDateEnd(e.target.value)}
            className="w-[110px] bg-transparent text-slate-300 [color-scheme:dark]"
            aria-label="Filter cases to date"
          />
          {(dateStart || dateEnd) && (
            <>
              <span className="ml-1 text-slate-500">{filteredGeojson.features.length} shown</span>
              <button
                type="button"
                onClick={() => { setDateStart(''); setDateEnd('') }}
                className="ml-1 text-slate-500 hover:text-slate-300"
                aria-label="Clear date filter"
              >
                ×
              </button>
            </>
          )}
        </div>
      </div>

      {showTools && <SpatialToolsPanel {...spatialTools} />}
    </div>
  )
}
