import React from 'react'
import {
  Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { tierBadge } from '@/lib/format'
import {
  confidenceTone, locString, hasCoords, sourceFamilyMeta, sourceLabel, sourceUrl,
} from '@/lib/ovnis-format'
import { cn } from '@/lib/utils'
import { useLocale } from '@/lib/locale'
import { useIsMobile } from '@/hooks/use-mobile'
import { ExternalLink } from 'lucide-react'

export default function CaseDetail({ case: c, onClose }) {
  const isMobile = useIsMobile()
  const { t } = useLocale()
  const agency = c ? sourceFamilyMeta(c.source_family) : null
  const link = c ? sourceUrl(c) : null
  return (
    <Sheet open={!!c} onOpenChange={(o) => !o && onClose?.()}>
      {/* Desktop: right-hand drawer. Mobile: a bottom sheet (no persistent
          inspector), capped so the map/list stays visible behind it and padded
          for the home indicator. */}
      <SheetContent
        side={isMobile ? 'bottom' : 'right'}
        className={cn(
          'bg-slate-950 border-slate-800 text-slate-200 overflow-y-auto',
          isMobile
            ? 'max-h-[85dvh] rounded-t-xl px-4 pb-[calc(1.5rem+var(--safe-bottom))]'
            : 'w-full sm:max-w-md',
        )}
      >
        {c && (
          <>
            <SheetHeader>
              <div className="flex items-center gap-2">
                <Badge variant="outline" className={cn('text-[10px]', tierBadge(c.evidence_tier))}>{c.evidence_tier}</Badge>
                <Badge variant="outline" className={cn('text-[10px]', confidenceTone(c.confidence))}>{c.confidence}</Badge>
                <span className="text-xs text-slate-500">{c.decade}</span>
              </div>
              <SheetTitle className="text-slate-100 text-left">{c.case_id} · {c.date_raw}</SheetTitle>
              <SheetDescription className="text-slate-400 text-left">{locString(c)}{!hasCoords(c) && ` · ${t('detail.noCoords')}`}</SheetDescription>
            </SheetHeader>

            <div className="mt-4 space-y-4 text-sm">
              <p className="text-slate-300 leading-relaxed">{c.description}</p>
              {c.description_en && c.description_en !== c.description && (
                <p className="text-slate-500 italic leading-relaxed">{c.description_en}</p>
              )}

              <Field label={t('detail.witness')}>
                {c.witness ? `${c.witness.class ?? '—'}${c.witness.count ? ` · ${c.witness.count}` : ''}${c.witness.name ? ` · ${c.witness.name}` : ''}` : '—'}
              </Field>
              <Field label={t('detail.evidenceType')}>{c.evidence_type ?? '—'}</Field>
              <Field label={t('detail.source')}>
                <div className="flex flex-wrap items-center gap-2">
                  {link ? (
                    <a
                      href={link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex min-w-0 items-center gap-1 text-sky-300 underline decoration-sky-500/50 underline-offset-2 hover:text-sky-200 break-all"
                    >
                      <span>{sourceLabel(c)}</span>
                      <ExternalLink className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
                    </a>
                  ) : (
                    <span className="break-words">{sourceLabel(c)}</span>
                  )}
                  {!link && (
                    <Badge variant="outline" className="text-[10px] bg-amber-500/10 text-amber-300 border-amber-500/30">
                      {t('cases.noUrl')}
                    </Badge>
                  )}
                </div>
              </Field>
              {agency && (
                <Field label={t('detail.agency')}>
                  <Badge variant="outline" className={cn('text-[10px]', agency.badge)}>{agency.label}</Badge>
                </Field>
              )}
              {c.contradictions_or_gaps ? (
                <Field label={t('detail.gaps')}><span className="text-amber-300/90">{c.contradictions_or_gaps}</span></Field>
              ) : null}
              <Field label={t('detail.provenance')}>
                <span className="text-xs text-slate-500">{c.reviewer_action} · {t('detail.from')} {c.promoted_from} · {c.promoted_at?.slice?.(0, 10)} · {c.promoted_by}</span>
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
