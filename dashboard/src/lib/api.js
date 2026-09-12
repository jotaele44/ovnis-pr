// REST client for the OVNIS FastAPI backend.
// Backend: server/backend/main.py  (uvicorn server.backend.main:app --port 8000)
// Reads the Git-native JSONL ledgers + release GeoJSON. 470 cases / 364 mapped.
import snapshot from './snapshot.json' // {} in normal builds; populated for VITE_OFFLINE exports
export const API_BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

// Offline export build: resolve from an embedded data snapshot instead of fetching.
// (A file:// page cannot fetch at all, so standalone exports bake the data in.)
const OFFLINE = import.meta.env.VITE_OFFLINE === '1'

/** Error carrying enough detail for the UI to say what went wrong. */
export class ApiError extends Error {
  constructor(message, { status = null, path = null, cause = null } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.path = path
    this.cause = cause
  }
}

// Throws on failure rather than returning a fallback.
//
// This previously swallowed both a non-2xx response and a thrown request into
// `fallback`, and every caller passed `[]` or a benign shape. Because the
// promise then *resolved*, react-query's `isError` was never true — the whole
// error path was dead code — and a backend outage rendered as
// "Queue empty" (CandidateReview.jsx) or an empty map. The operator was shown a
// confident, wrong answer: "there is nothing here" instead of "I could not ask".
//
// Failing loudly restores react-query's retry and error handling, and callers
// distinguish the two states with `isError` vs. an genuinely empty array.
async function getJSON(path) {
  if (OFFLINE) {
    const key = path.split('?')[0] // server-side filters degrade to the unfiltered snapshot
    if (key in snapshot) return snapshot[key]
    // A missing snapshot key in an offline build is a build defect, not an
    // outage — but it is still not data, so it must not read as empty either.
    throw new ApiError(`No offline snapshot for ${key}`, { path: key })
  }
  let res
  try {
    res = await fetch(`${API_BASE}${path}`, { signal: AbortSignal.timeout(8000) })
  } catch (cause) {
    throw new ApiError(
      cause?.name === 'TimeoutError'
        ? `Request to ${path} timed out after 8s`
        : `Could not reach the backend at ${API_BASE}`,
      { path, cause },
    )
  }
  if (!res.ok) {
    throw new ApiError(`Backend returned ${res.status} for ${path}`, { status: res.status, path })
  }
  return res.json()
}

const qs = (params) => {
  const p = Object.entries(params).filter(([, v]) => v != null && v !== '')
  return p.length ? '?' + new URLSearchParams(p).toString() : ''
}

export const getHealth = () => getJSON('/health')
export const getCases = (f = {}) => getJSON(`/cases${qs(f)}`)
export const getCase = (id) => getJSON(`/cases/${encodeURIComponent(id)}`)
export const getCandidates = () => getJSON('/candidates')
export const getGeojson = () => getJSON('/geojson')
export const getStats = () => getJSON('/stats')
export const search = (q) => getJSON(`/search${qs({ q })}`)
export const getMunicipiosCaseDensity = () => getJSON('/municipios/case_density')
