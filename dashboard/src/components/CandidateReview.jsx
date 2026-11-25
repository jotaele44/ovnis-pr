import React from 'react'
import { federationTone, FederationEmptyState } from '@pr-federation/react'
import { useCandidates } from '@/lib/hooks'
import QueryState from '@/components/QueryState'
import { Badge } from '@/components/ui/badge'
import { tierBadge } from '@/lib/format'
import { locString } from '@/lib/ovnis-format'
import { cn, lookup } from '@/lib/utils'
import { scrollRegion } from '@/lib/scrollRegion'

// Map this app's candidate review-status vocabulary onto the canonical
// federation status roles (see @pr-federation/react). Colors now come from the
// shared design system's `.fd-status` tokens instead of hard-coded Tailwind
// tone literals.
const STATUS_ROLE = {
  pending: 'warning',
  monitoring: 'info',
  promoted: 'success',
  merged: 'process',
  rejected_to_echoes: 'danger',
}

// Candidate intake queue (awaiting promotion to master).
export default function CandidateReview() {
  const { data: candidates = [], isLoading, isError, error, refetch } = useCandidates()

  // The count line asserts a fact about the queue, so it must not render while
  // the queue is unknown — "0 candidates in queue" was the same lie as
  // "Queue empty".
  if (isLoading || isError) {
    return (
      <div {...scrollRegion("Candidates")} className="h-full overflow-auto p-2">
        <QueryState loading={isLoading} error={isError ? error : null} onRetry={refetch} />
      </div>
    )
  }

  return (
    <div {...scrollRegion("Candidate list")} className="h-full overflow-auto p-2 space-y-1.5">
      <div className="px-1 pb-1 text-xs text-slate-400">{candidates.length} candidates in queue</div>
      {candidates.map((c) => (
        <div key={c.candidate_id} className="rounded-md border border-slate-800 bg-slate-900 p-2.5">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-mono text-slate-300">{c.candidate_id}</span>
            {c.evidence_tier && <Badge variant="outline" className={cn('text-[10px]', tierBadge(c.evidence_tier))}>{c.evidence_tier}</Badge>}
            {(() => {
              const { className: fdClass, ...toneAttrs } = federationTone(lookup(STATUS_ROLE, c.review_status, 'neutral'))
              return (
                <span className={`${fdClass} text-[10px]`} {...toneAttrs}>
                  {c.review_status ?? 'pending'}
                </span>
              )
            })()}
            {c.intake_channel && <span className="text-[10px] text-slate-400">{c.intake_channel}</span>}
          </div>
          <p className="text-xs text-slate-300 mt-1 line-clamp-2">{c.description}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">{c.date_raw || '—'} · {locString(c)}</p>
        </div>
      ))}
      {/* Reached only when the fetch succeeded, so an empty queue here is a
          real fact about the data rather than a swallowed failure. */}
      {candidates.length === 0 && <FederationEmptyState className="py-8" title="Queue empty" />}
    </div>
  )
}
