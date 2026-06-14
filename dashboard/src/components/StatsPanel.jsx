import { useStats } from '@/lib/hooks'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Cell,
} from 'recharts'
import { tierHex } from '@/lib/prufon-format'

function toData(obj = {}) {
  return Object.entries(obj).map(([name, value]) => ({ name, value }))
}

export default function StatsPanel() {
  const { data: stats } = useStats()
  const s = stats ?? {}
  const decades = toData(s.byDecade).sort((a, b) => a.name.localeCompare(b.name))
  const tiers = ['T1', 'T2', 'T3', 'T4'].map((t) => ({ name: t, value: s.byTier?.[t] ?? 0 }))

  return (
    <div className="h-full overflow-auto p-3 space-y-3">
      <div className="grid grid-cols-3 gap-2">
        <Kpi label="Total" value={s.total} />
        <Kpi label="Mapped" value={s.mapped} />
        <Kpi label="Unmapped" value={s.unmapped} tone="text-amber-300" />
      </div>

      <Card title="Cases by decade">
        <div className="h-44">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={decades} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 10 }} interval={0} angle={-35} textAnchor="end" height={42} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 6, fontSize: 12 }} />
              <Bar dataKey="value" fill="#a78bfa" radius={[3, 3, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>

      <Card title="Cases by evidence tier">
        <div className="h-40">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={tiers} margin={{ top: 4, right: 8, bottom: 4, left: -20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
              <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} allowDecimals={false} />
              <Tooltip contentStyle={{ background: '#0f172a', border: '1px solid #1e293b', borderRadius: 6, fontSize: 12 }} />
              <Bar dataKey="value" radius={[3, 3, 0, 0]}>
                {tiers.map((t) => <Cell key={t.name} fill={tierHex(t.name)} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  )
}

function Kpi({ label, value, tone = 'text-slate-100' }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-900 p-2 text-center">
      <div className={`text-lg font-semibold ${tone}`}>{value ?? '–'}</div>
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
    </div>
  )
}

function Card({ title, children }) {
  return (
    <div className="rounded-md border border-slate-800 bg-slate-900 p-3">
      <h4 className="text-xs uppercase tracking-wide text-slate-500 mb-2">{title}</h4>
      {children}
    </div>
  )
}
