// OVNIS display helpers. Evidence tier T1 (strongest) → T4 (weakest).

const TIER_HEX = { T1: '#38bdf8', T2: '#818cf8', T3: '#a78bfa', T4: '#64748b' }
export const tierHex = (t) => TIER_HEX[t] ?? '#64748b'

const CONFIDENCE_TONE = {
  high: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  'medium-high': 'bg-teal-500/15 text-teal-300 border-teal-500/30',
  medium: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  'low-medium': 'bg-orange-500/15 text-orange-300 border-orange-500/30',
  low: 'bg-red-500/15 text-red-300 border-red-500/30',
}
export const confidenceTone = (c) =>
  CONFIDENCE_TONE[c] ?? 'bg-slate-500/15 text-slate-300 border-slate-500/30'

export function locString(c) {
  const l = c.location || {}
  return l.string || c.location_string || l.municipality || '—'
}
export const hasCoords = (c) => {
  const l = c.location || {}
  return l.lat != null && l.lon != null
}
