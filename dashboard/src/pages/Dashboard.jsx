import { useState } from 'react'
import { useGeojson, useCases, useHealth } from '@/lib/hooks'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import CaseMap from '@/components/CaseMap'
import CaseGrid from '@/components/CaseGrid'
import CaseDetail from '@/components/CaseDetail'
import StatsPanel from '@/components/StatsPanel'
import CandidateReview from '@/components/CandidateReview'
import ProgramTimeline from '@/components/ProgramTimeline'
import brandMark from "@/assets/icon-64.png?inline";

const PROGRAM_TIMELINE = [
  { id:'ovnis-sweep', phase:'NOW', title:'Primary-source case sweep', detail:'Search government, archival, maritime, aviation, and local records for new Puerto Rico UAP/USO evidence.', category:'Discovery' },
  { id:'ovnis-intake', phase:'NEXT', title:'Evidence intake', detail:'Freeze source manifestations, transcribe records, and preserve exact provenance before interpretation.', category:'Evidence' },
  { id:'ovnis-dedupe', phase:'NEXT', title:'Identity and duplicate adjudication', detail:'Separate candidate events, aliases, and source manifestations without merging on name/date proximity.', category:'Review' },
  { id:'ovnis-timeline', phase:'QUEUED', title:'Chronology reconciliation', detail:'Bind validated events into the historical timeline while preserving unresolved contradictions.', category:'Timeline' },
  { id:'ovnis-cert', phase:'BLOCKED', title:'Corpus certification', detail:'Final promotion waits on source closure, duplicate/edge adjudication, and zero unresolved residue in scope.', category:'Certification' },
]

export default function Dashboard() {
  const { data: geojson } = useGeojson()
  const { data: cases = [] } = useCases()
  const { data: health, isError: healthError, isLoading: healthLoading } = useHealth()
  const [selected, setSelected] = useState(null)

  const up = !healthError && health?.status === 'ok'
  // Three states, not two. "connecting…" was shown indefinitely once the health
  // request started failing, so an unreachable backend looked like a slow one.
  const healthLabel = healthError
    ? 'backend unreachable'
    : healthLoading || !health
      ? 'connecting…'
      : `${health.master} cases · ${health.mapped} mapped · ${health.unmapped} unmapped`
  const selectByProps = (props) => {
    const full = cases.find((c) => c.case_id === props.case_id)
    setSelected(full ?? props)
  }

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-200">
      <header className="flex items-center gap-2 px-4 py-2.5 border-b border-slate-800 bg-slate-900">
        <img src={brandMark} alt="" aria-hidden="true" className="h-6 w-6 rounded-md" />
        <div className="flex-1">
          <h1 className="text-sm font-semibold text-slate-100 leading-none">OVNIS · Ovnis-PR</h1>
          <p className="text-[11px] text-slate-500 mt-0.5">Puerto Rico UAP sighting registry & witness review</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className={`inline-flex h-2 w-2 rounded-full ${up ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          <span role={healthError ? 'alert' : undefined}>{healthLabel}</span>
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
            <TabsList className="grid grid-cols-4 mx-2 mt-2 bg-slate-900">
              <TabsTrigger value="cases" className="text-xs">Cases</TabsTrigger>
              <TabsTrigger value="stats" className="text-xs">Statistics</TabsTrigger>
              <TabsTrigger value="candidates" className="text-xs">Candidates</TabsTrigger>
              <TabsTrigger value="activity" className="text-xs">Activity</TabsTrigger>
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
            <TabsContent value="activity" className="flex-1 min-h-0 mt-2 overflow-y-auto p-2">
              <ProgramTimeline items={PROGRAM_TIMELINE} />
            </TabsContent>
          </Tabs>
        </aside>
      </div>

      <CaseDetail case={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
