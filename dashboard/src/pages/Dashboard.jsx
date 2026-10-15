import styles from '../zip-design/Overview.module.css'
import { useState } from 'react'
import { useGeojson, useCases, useHealth } from '@/lib/hooks'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import CaseMap from '@/components/CaseMap'
import CaseGrid from '@/components/CaseGrid'
import CaseDetail from '@/components/CaseDetail'
import StatsPanel from '@/components/StatsPanel'
import CandidateReview from '@/components/CandidateReview'
import brandMark from "@/assets/icon-64.png?inline";

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
    <div className={`zip-surface ${styles.app}`}>
      <header className={styles.header}>
        <img src={brandMark} alt="" aria-hidden="true" className="h-6 w-6 rounded-md" />
        <div className={styles.brandCopy}>
          <h1 className="text-sm font-semibold text-slate-100 leading-none">OVNIS · Ovnis-PR</h1>
          <p className="text-[11px] text-slate-500 mt-0.5">Puerto Rico UAP sighting registry & witness review</p>
        </div>
        <div className={styles.health}>
          <span className={`inline-flex h-2 w-2 rounded-full ${up ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
          <span role={healthError ? 'alert' : undefined}>{healthLabel}</span>
        </div>
      </header>

      <div className={styles.workspace}>
        <div className={styles.mapPane}>
          <CaseMap geojson={geojson} onSelect={selectByProps} />
          <div className={styles.mapLegend}>
            {geojson?.features?.length ?? 0} mapped sightings · colored by evidence tier
          </div>
        </div>

        <aside className={`${styles.sidePane} flex flex-col`}>
          <Tabs defaultValue="cases" className={`${styles.tabsRoot} flex flex-col flex-1 min-h-0`}>
            <TabsList className="grid grid-cols-3 mx-2 mt-2 bg-slate-900">
              <TabsTrigger value="cases" className="text-xs">Cases</TabsTrigger>
              <TabsTrigger value="stats" className="text-xs">Statistics</TabsTrigger>
              <TabsTrigger value="candidates" className="text-xs">Candidates</TabsTrigger>
            </TabsList>
            <TabsContent value="cases" className={`${styles.tabContent} flex-1 min-h-0 mt-2`}>
              <CaseGrid cases={cases} selectedId={selected?.case_id} onSelect={setSelected} />
            </TabsContent>
            <TabsContent value="stats" className={`${styles.tabContent} flex-1 min-h-0 mt-2`}>
              <StatsPanel />
            </TabsContent>
            <TabsContent value="candidates" className={`${styles.tabContent} flex-1 min-h-0 mt-2`}>
              <CandidateReview />
            </TabsContent>
          </Tabs>
        </aside>
      </div>

      <CaseDetail case={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
