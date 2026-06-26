import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { tierBadge } from '@/lib/format'
import { confidenceTone, locString, hasCoords } from '@/lib/ovnis-format'
import { cn } from '@/lib/utils'

export default function CaseDetail({ case: c, onClose }) {
  return (
    <Sheet open={!!c} onOpenChange={(o) => !o && onClose?.()}>
      <SheetContent className="bg-slate-950 border-slate-800 text-slate-200 w-full sm:max-w-md overflow-y-auto">
        {c && (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={cn('text-[10px]', tierBadge(c.evidence_tier))}>{c.evidence_tier}</Badge>
                <Badge variant="outline" className={cn('text-[10px]', confidenceTone(c.confidence))}>{c.confidence}</Badge>
                <span className="text-xs text-slate-500">{c.decade}</span>
              </div>
              <SheetTitle className="text-slate-100 text-left">{c.case_id} · {c.date_raw}</SheetTitle>
              <SheetDescription className="text-slate-400 text-left">{locString(c)}{!hasCoords(c) && ' · (no coordinates)'}</SheetDescription>
            </SheetHeader>

            <div className="mt-4 space-y-4 text-sm">
              <p className="text-slate-300 leading-relaxed">{c.description}</p>
              {c.description_en && c.description_en !== c.description && (
                <p className="text-slate-500 italic leading-relaxed">{c.description_en}</p>
              )}

              <Field label="Witness">
                {c.witness ? `${c.witness.class ?? '—'}${c.witness.count ? ` · ${c.witness.count}` : ''}${c.witness.name ? ` · ${c.witness.name}` : ''}` : '—'}
              </Field>
              <Field label="Evidence type">{c.evidence_type ?? '—'}</Field>
              <Field label="Source">{c.source ?? '—'}</Field>
              {c.contradictions_or_gaps ? (
                <Field label="Contradictions / gaps"><span className="text-amber-300/90">{c.contradictions_or_gaps}</span></Field>
              ) : null}
              <Field label="Provenance">
                <span className="text-xs text-slate-500">{c.reviewer_action} · from {c.promoted_from} · {c.promoted_at?.slice?.(0, 10)} · {c.promoted_by}</span>
              </Field>
            </div>
          </>
        )}
      </SheetContent>
    </Sheet>
  )
}

function Field({ label, children }) {
  return (
    <div className="space-y-0.5 border-t border-slate-900 pt-2">
      <div className="text-[11px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="text-slate-200">{children}</div>
    </div>
  )
}
