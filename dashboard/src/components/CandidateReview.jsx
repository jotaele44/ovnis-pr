import { useCandidates } from '@/lib/hooks'
import { Badge } from '@/components/ui/badge'
import { tierBadge } from '@/lib/format'
import { locString } from '@/lib/ovnis-format'
import { cn } from '@/lib/utils'

const STATUS_TONE = {
  pending: 'bg-amber-500/15 text-amber-300 border-amber-500/30',
  monitoring: 'bg-sky-500/15 text-sky-300 border-sky-500/30',
  promoted: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  merged: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  rejected_to_echoes: 'bg-red-500/15 text-red-300 border-red-500/30',
}

// Candidate intake queue (awaiting promotion to master).
export default function CandidateReview() {
  const { data: candidates = [] } = useCandidates()

  return (
    <div className="h-full overflow-auto p-2 space-y-1.5">
      <div className="px-1 pb-1 text-xs text-slate-400">{candidates.length} candidates in queue</div>
      {candidates.map((c) => (
        <div key={c.candidate_id} className="rounded-md border border-slate-800 bg-slate-900 p-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono text-slate-300">{c.candidate_id}</span>
            {c.evidence_tier && <Badge variant="outline" className={cn('text-[10px]', tierBadge(c.evidence_tier))}>{c.evidence_tier}</Badge>}
            <Badge variant="outline" className={cn('text-[10px]', STATUS_TONE[c.review_status] ?? 'border-slate-700 text-slate-400')}>
              {c.review_status ?? 'pending'}
            </Badge>
            {c.intake_channel && <span className="text-[10px] text-slate-600">{c.intake_channel}</span>}
          </div>
          <p className="text-xs text-slate-300 mt-1 line-clamp-2">{c.description}</p>
          <p className="text-[11px] text-slate-500 mt-0.5">{c.date_raw || '—'} · {locString(c)}</p>
        </div>
      ))}
      {candidates.length === 0 && <p className="text-center text-sm text-slate-500 py-8">Queue empty</p>}
    </div>
  )
}
