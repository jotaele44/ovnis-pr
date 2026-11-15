import { useState } from 'react'
import { useGeojson, useCases, useHealth } from '@/lib/hooks'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import CaseMap from '@/components/CaseMap'
import CaseGrid from '@/components/CaseGrid'
import CaseDetail from '@/components/CaseDetail'
import StatsPanel from '@/components/StatsPanel'
import CandidateReview from '@/components/CandidateReview'
import ProgramTimeline from '@/components/ProgramTimeline'
import MobileNav from '@/components/MobileNav'
import TopControls from '@/components/TopControls'
import { useIsMobile } from '@/hooks/use-mobile'
import { useLocale } from '@/lib/locale'
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
  const [view, setView] = useState('cases')
  const isMobile = useIsMobile()
  const { t } = useLocale()

  const up = !healthError && health?.status === 'ok'
  // Three states, not two. "connecting…" was shown indefinitely once the health
  // request started failing, so an unreachable backend looked like a slow one.
  const healthLabel = healthError
    ? t('health.unreachable')
    : healthLoading || !health
      ? t('health.connecting')
      : t('health.summary', { master: health.master, mapped: health.mapped, unmapped: health.unmapped })
  const selectByProps = (props) => {
    const full = cases.find((c) => c.case_id === props.case_id)
    setSelected(full ?? props)
  }

  const mapLegend = (
    <div className="pointer-events-none absolute bottom-2 left-2 rounded bg-slate-900/80 px-2 py-1 text-[11px] text-slate-400">
      {t('map.legend', { count: geojson?.features?.length ?? 0 })}
    </div>
  )

  return (
    <div className="flex flex-col h-dvh bg-slate-950 text-slate-200 pl-[var(--safe-left)] pr-[var(--safe-right)]">
      {/* Sticky header: 54px + the top safe area (notch / status bar). On a phone
          the health text collapses to its dot (the text moves to the More sheet and
          stays available to screen readers) so the controls fit at 390px. */}
      <header className="shrink-0 flex items-center gap-2 border-b border-slate-800 bg-slate-900 px-3 pt-[var(--safe-top)] min-h-[calc(var(--header-h)+var(--safe-top))] shell-desktop:px-4">
        <img src={brandMark} alt="" aria-hidden="true" className="h-6 w-6 rounded-md" />
        <div className="min-w-0 flex-1">
          <h1 className="text-sm font-semibold text-slate-100 leading-none">OVNIS · Ovnis-PR</h1>
          <p className="mt-0.5 truncate text-[11px] text-slate-500">{t('app.subtitle')}</p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span className={`inline-flex h-2 w-2 shrink-0 rounded-full ${up ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          <span role={healthError ? 'alert' : undefined} className={isMobile ? 'sr-only' : undefined}>{healthLabel}</span>
        </div>
        <TopControls />
      </header>

      {isMobile ? (
        <>
          <main className="relative flex-1 min-h-0">
            {/* The case list stays mounted so its search, filters and page survive a
                trip to another view; the others mount on demand. */}
            <section hidden={view !== 'cases'} className="h-full">
              <CaseGrid cases={cases} selectedId={selected?.case_id} onSelect={setSelected} />
            </section>
            {view === 'map' && (
              <section className="relative h-full">
                <CaseMap geojson={geojson} onSelect={selectByProps} />
                {mapLegend}
              </section>
            )}
            {view === 'stats' && <section className="h-full"><StatsPanel /></section>}
            {view === 'candidates' && <section className="h-full"><CandidateReview /></section>}
            {view === 'activity' && (
              <section className="h-full overflow-y-auto p-3">
                <ProgramTimeline producerId="ovnis-pr" items={PROGRAM_TIMELINE} compact />
              </section>
            )}
          </main>
          <MobileNav view={view} onChange={setView} status={healthLabel} />
        </>
      ) : (
        <div className="flex flex-1 min-h-0">
          <div className="relative flex-1 min-w-0">
            <CaseMap geojson={geojson} onSelect={selectByProps} />
            {mapLegend}
          </div>

          <aside className="w-[440px] shrink-0 border-l border-slate-800 bg-slate-950 flex flex-col min-h-0">
            <Tabs defaultValue="cases" className="flex flex-col flex-1 min-h-0">
              <TabsList className="grid grid-cols-4 mx-2 mt-2 bg-slate-900">
                <TabsTrigger value="cases" className="text-xs">{t('nav.cases')}</TabsTrigger>
                <TabsTrigger value="stats" className="text-xs">{t('nav.stats')}</TabsTrigger>
                <TabsTrigger value="candidates" className="text-xs">{t('nav.candidates')}</TabsTrigger>
                <TabsTrigger value="activity" className="text-xs">{t('nav.activity')}</TabsTrigger>
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
                <ProgramTimeline producerId="ovnis-pr" items={PROGRAM_TIMELINE} compact />
              </TabsContent>
            </Tabs>
          </aside>
        </div>
      )}

      <CaseDetail case={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
