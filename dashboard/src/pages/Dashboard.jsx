import { useState } from 'react'
import { useGeojson, useCases, useHealth } from '@/lib/hooks'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import CaseMap from '@/components/CaseMap'
import CaseGrid from '@/components/CaseGrid'
import CaseDetail from '@/components/CaseDetail'
import StatsPanel from '@/components/StatsPanel'
import CandidateReview from '@/components/CandidateReview'
import { Telescope } from 'lucide-react'

export default function Dashboard() {
  const { data: geojson } = useGeojson()
  const { data: cases = [] } = useCases()
  const { data: health } = useHealth()
  const [selected, setSelected] = useState(null)

  const up = health?.status === 'ok'
  const selectByProps = (props) => {
    const full = cases.find((c) => c.case_id === props.case_id)
    setSelected(full ?? props)
  }

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-200">
      <header className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-800 bg-slate-900">
        <Telescope className="h-5 w-5 text-violet-400" />
        <div className="flex-1">
          <h1 className="text-sm font-semibold text-slate-100 leading-none">PRUFON · Ovnis-PR</h1>
          <p className="text-[11px] text-slate-500 mt-0.5">Puerto Rico UAP sighting registry & witness review</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className={`inline-flex h-2 w-2 rounded-full ${up ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          {health ? `${health.master} cases · ${health.mapped} mapped · ${health.unmapped} unmapped` : 'connecting…'}
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <div className="relative flex-1 min-w-0">
          <CaseMap geojson={geojson} onSelect={selectByProps} />
          <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-slate-900/80 px-2 py-1 text-[11px] text-slate-400">
            {geojson?.features?.length ?? 0} mapped sightings · colored by evidence tier
          </div>
        </div>

        <aside className="w-[440px] shrink-0 border-l border-slate-800 bg-slate-950 flex flex-col min-h-0">
          <Tabs defaultValue="cases" className="flex flex-col flex-1 min-h-0">
            <TabsList className="grid grid-cols-3 mx-2 mt-2 bg-slate-900">
              <TabsTrigger value="cases" className="text-xs">Cases</TabsTrigger>
              <TabsTrigger value="stats" className="text-xs">Statistics</TabsTrigger>
              <TabsTrigger value="candidates" className="text-xs">Candidates</TabsTrigger>
            </TabsList>
            <TabsContent value="cases" className="flex-1 min-h-0 mt-2">
              <CaseGrid cases={cases} selectedId={selected?.case_id} onSelect={setSelected} />
            </TabsContent>
            <TabsContent value="stats" className="flex-1 min-h-0 mt-2">
              <StatsPanel />
            </TabsContent>
            <TabsContent value="candidates" className="flex-1 min-h-0 mt-2">
              <CandidateReview />
            </TabsContent>
          </Tabs>
        </aside>
      </div>

      <CaseDetail case={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
