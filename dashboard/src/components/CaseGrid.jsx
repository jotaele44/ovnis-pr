import { useEffect, useMemo, useRef, useState } from 'react'
import { FederationEmptyState } from '@pr-federation/react'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'
import {
  Pagination, PaginationContent, PaginationItem,
} from '@/components/ui/pagination'
import { tierBadge } from '@/lib/format'
import { locString, hasCoords, hasSourceUrl, sourceFamilyMeta } from '@/lib/ovnis-format'
import { useLocale } from '@/lib/locale'
import { useIsMobile } from '@/hooks/use-mobile'
import { cn } from '@/lib/utils'
import { ChevronLeft, ChevronRight, MapPin, MapPinOff, X } from 'lucide-react'

export const PAGE_SIZES = [12, 24, 48, 100]
export const DEFAULT_PAGE_SIZE = PAGE_SIZES[0]
const TIERS = ['T1', 'T2', 'T3', 'T4']

// What the search box matches: the case id, the year/date as written, the decade,
// both descriptions, the place and the agency label. The id/year/agency were not
// searchable before, so typing "1976" or "FBI" found nothing unless the word
// happened to appear in the description.
export function searchText(c) {
  return [
    c.case_id, c.date_raw, c.decade, c.description, c.description_en,
    locString(c), sourceFamilyMeta(c.source_family)?.label,
  ].filter(Boolean).join(' ').toLowerCase()
}

export function filterCases(cases, { decade = 'all', tier = 'all', q = '' } = {}) {
  const needle = q.trim().toLowerCase()
  return cases.filter((c) =>
    (decade === 'all' || c.decade === decade) &&
    (tier === 'all' || c.evidence_tier === tier) &&
    (!needle || searchText(c).includes(needle)))
}

export function pageSlice(rows, page, pageSize) {
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize))
  const current = Math.min(Math.max(page, 0), pageCount - 1)
  return { current, pageCount, items: rows.slice(current * pageSize, (current + 1) * pageSize) }
}

// All 470 master cases (includes cases without coordinates or source URLs,
// both flagged inline rather than hidden). Rendered as a table in the desktop
// side pane and as touch cards on the mobile shell; filters and paging are shared.
export default function CaseGrid({ cases = [], selectedId, onSelect }) {
  const isMobile = useIsMobile()
  const { t } = useLocale()
  const [decade, setDecade] = useState('all')
  const [tier, setTier] = useState('all')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(0)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const scrollRef = useRef(null)

  const decades = useMemo(
    () => ['all', ...Array.from(new Set(cases.map((c) => c.decade).filter(Boolean))).sort()],
    [cases],
  )

  const rows = useMemo(() => filterCases(cases, { decade, tier, q }), [cases, decade, tier, q])
  const { current, pageCount, items } = pageSlice(rows, page, pageSize)

  // A new page (or page size) starts at the top of the list, not mid-scroll.
  useEffect(() => {
    scrollRef.current?.scrollTo?.({ top: 0 })
  }, [current, pageSize])

  const change = (setter) => (value) => {
    setter(value)
    setPage(0)
  }
  const reset = () => {
    setQ('')
    setDecade('all')
    setTier('all')
    setPage(0)
  }

  const periodLabel = t('cases.period')
  const tierLabel = t('cases.tier')
  const chips = [
    q.trim() && { key: 'q', label: `“${q.trim()}”`, clear: () => change(setQ)('') },
    decade !== 'all' && { key: 'decade', label: `${periodLabel}: ${decade}`, clear: () => change(setDecade)('all') },
    tier !== 'all' && { key: 'tier', label: `${tierLabel}: ${tier}`, clear: () => change(setTier)('all') },
  ].filter(Boolean)

  const fieldH = isMobile ? 'h-11 text-base' : 'h-7 text-xs'

  const search = (
    <Input
      type="search"
      value={q}
      onChange={(e) => change(setQ)(e.target.value)}
      placeholder={t('cases.search.placeholder')}
      aria-label={t('cases.search.label')}
      enterKeyHint="search"
      className={cn('flex-1 bg-slate-950 border-slate-800', fieldH)}
    />
  )
  const decadeSelect = (
    <Select value={decade} onValueChange={change(setDecade)}>
      <SelectTrigger aria-label={periodLabel} className={cn(isMobile ? 'w-full' : 'w-[100px]', fieldH)}><SelectValue /></SelectTrigger>
      <SelectContent>
        {decades.map((d) => (
          <SelectItem key={d} value={d} className={isMobile ? 'min-h-11 text-base' : 'text-xs'}>
            {d === 'all' ? t('cases.allPeriods') : d}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
  const tierSelect = (
    <Select value={tier} onValueChange={change(setTier)}>
      <SelectTrigger aria-label={tierLabel} className={cn(isMobile ? 'w-full' : 'w-[90px]', fieldH)}><SelectValue /></SelectTrigger>
      <SelectContent>
        {['all', ...TIERS].map((x) => (
          <SelectItem key={x} value={x} className={isMobile ? 'min-h-11 text-base' : 'text-xs'}>
            {x === 'all' ? t('cases.allTiers') : x}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )

  return (
    <div className="flex flex-col h-full min-h-0">
      {isMobile ? (
        <div className="space-y-2 p-3 pb-2 short:grid short:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_minmax(0,1fr)] short:items-end short:gap-2 short:space-y-0">
          <label className="block space-y-1">
            <span className="text-xs font-medium text-slate-400">{t('cases.search.label')}</span>
            <div className="flex">{search}</div>
          </label>
          <div className="grid grid-cols-2 gap-2 short:contents">
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-400">{periodLabel}</span>
              {decadeSelect}
            </div>
            <div className="space-y-1">
              <span className="text-xs font-medium text-slate-400">{tierLabel}</span>
              {tierSelect}
            </div>
          </div>
        </div>
      ) : (
        <div className="flex items-center gap-2 p-2">
          {search}
          {decadeSelect}
          {tierSelect}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 px-3 pb-2 shell-desktop:px-2 text-xs text-slate-400">
        <p aria-live="polite">
          <span data-testid="case-count" className="font-semibold text-slate-200">{rows.length}</span>{' '}
          {t('cases.ofTotal', { total: cases.length })}
        </p>
        {chips.map((chip) => (
          <button
            key={chip.key}
            type="button"
            onClick={chip.clear}
            aria-label={t('cases.removeFilter', { label: chip.label })}
            className={cn(
              'inline-flex items-center gap-1 rounded-full border border-slate-700 bg-slate-900 px-2.5 text-slate-200 hover:bg-slate-800',
              isMobile ? 'min-h-11 px-3' : 'min-h-6',
            )}
          >
            <span className="max-w-[12rem] truncate">{chip.label}</span>
            <X className="h-3 w-3 shrink-0" aria-hidden="true" />
          </button>
        ))}
      </div>

      <div ref={scrollRef} className="flex-1 min-h-0 overflow-auto">
        {rows.length === 0 ? (
          <FederationEmptyState
            className="py-8"
            title={t('cases.empty.title')}
            description={t('cases.empty.description')}
            action={
              <Button type="button" variant="outline" onClick={reset} className={isMobile ? 'h-11 text-base' : undefined}>
                {t('cases.reset')}
              </Button>
            }
          />
        ) : isMobile ? (
          <ul aria-label={t('cases.list')} className="space-y-2 px-3 pb-3">
            {items.map((c) => (
              <li key={c.case_id}>
                <CaseCard c={c} selected={selectedId === c.case_id} onSelect={onSelect} t={t} />
              </li>
            ))}
          </ul>
        ) : (
          <CaseTable items={items} selectedId={selectedId} onSelect={onSelect} t={t} />
        )}
      </div>

      {rows.length > 0 && (
        <div className="flex shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-t border-slate-800 px-3 py-2 shell-desktop:px-2">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span id="case-page-size-label">{t('cases.perPage')}</span>
            <Select value={String(pageSize)} onValueChange={(v) => change(setPageSize)(Number(v))}>
              <SelectTrigger aria-labelledby="case-page-size-label" className={cn('w-[72px]', fieldH)}><SelectValue /></SelectTrigger>
              <SelectContent>
                {PAGE_SIZES.map((n) => (
                  <SelectItem key={n} value={String(n)} className={isMobile ? 'min-h-11 text-base' : 'text-xs'}>{n}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Pagination aria-label={t('cases.pagination')} className="mx-0 w-auto">
            <PaginationContent>
              <PaginationItem>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  disabled={current === 0}
                  onClick={() => setPage(current - 1)}
                  aria-label={t('cases.prev')}
                  className={isMobile ? 'h-11 w-11' : 'h-7 w-7'}
                >
                  <ChevronLeft className="h-4 w-4" aria-hidden="true" />
                </Button>
              </PaginationItem>
              <PaginationItem>
                <span className="px-1 text-xs text-slate-400" aria-live="polite">
                  {t('cases.pageOf', { page: current + 1, pages: pageCount })}
                </span>
              </PaginationItem>
              <PaginationItem>
                <Button
                  type="button"
                  variant="outline"
                  size="icon"
                  disabled={current >= pageCount - 1}
                  onClick={() => setPage(current + 1)}
                  aria-label={t('cases.next')}
                  className={isMobile ? 'h-11 w-11' : 'h-7 w-7'}
                >
                  <ChevronRight className="h-4 w-4" aria-hidden="true" />
                </Button>
              </PaginationItem>
            </PaginationContent>
          </Pagination>
        </div>
      )}
    </div>
  )
}

// One case as a touch card: identity (id, date, place) and status (tier, agency,
// missing URL / coordinates) in the primary view; the full record opens in the
// bottom sheet on tap.
function CaseCard({ c, selected, onSelect, t }) {
  const agency = sourceFamilyMeta(c.source_family)
  return (
    <button
      type="button"
      onClick={() => onSelect?.(c)}
      aria-pressed={selected}
      className={cn(
        'block min-h-[44px] w-full rounded-lg border p-3 text-left transition-colors',
        selected ? 'border-violet-500/50 bg-violet-500/10' : cn('border-slate-800 hover:bg-slate-800/50', agency?.rowTint),
      )}
    >
      <span className="flex items-start justify-between gap-2">
        <span className="min-w-0">
          <span className="block truncate font-mono text-sm text-slate-100">{c.case_id}</span>
          <span className="block text-xs text-slate-400">{c.date_raw}</span>
        </span>
        <Badge variant="outline" className={cn('shrink-0 text-xs', tierBadge(c.evidence_tier))}>{c.evidence_tier}</Badge>
      </span>
      <span className="mt-1.5 flex items-center gap-1.5 text-sm text-slate-300">
        {!hasCoords(c) && <MapPinOff className="h-3.5 w-3.5 shrink-0 text-slate-600" aria-label={t('cases.noCoords')} />}
        {hasCoords(c) && <MapPin className="h-3.5 w-3.5 shrink-0 text-slate-500" aria-hidden="true" />}
        <span className="min-w-0 truncate">{locString(c)}</span>
      </span>
      {(agency || !hasSourceUrl(c)) && (
        <span className="mt-2 flex flex-wrap items-center gap-1.5">
          {agency && (
            <Badge variant="outline" className={cn('max-w-full truncate text-[11px]', agency.badge)}>{agency.label}</Badge>
          )}
          {!hasSourceUrl(c) && (
            <span className="rounded border border-amber-500/30 px-1.5 text-[11px] leading-5 text-amber-300">{t('cases.noUrl')}</span>
          )}
        </span>
      )}
    </button>
  )
}

function CaseTable({ items, selectedId, onSelect, t }) {
  return (
    <Table>
      <TableHeader className="sticky top-0 bg-slate-900 z-10">
        <TableRow className="hover:bg-transparent border-slate-800">
          <TableHead className="text-slate-400">{t('cases.col.case')}</TableHead>
          <TableHead className="text-slate-400">{t('cases.col.date')}</TableHead>
          <TableHead className="text-slate-400">{t('cases.col.location')}</TableHead>
          <TableHead className="text-slate-400">{t('cases.col.agency')}</TableHead>
          <TableHead className="text-slate-400">{t('cases.col.tier')}</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {items.map((c) => {
          const agency = sourceFamilyMeta(c.source_family)
          return (
            <TableRow
              key={c.case_id}
              onClick={() => onSelect?.(c)}
              className={cn(
                'cursor-pointer border-slate-800',
                selectedId === c.case_id ? 'bg-violet-500/10' : agency?.rowTint,
                selectedId !== c.case_id && 'hover:bg-slate-800/50',
              )}
            >
              <TableCell className="text-xs text-slate-200 whitespace-nowrap">
                <span className="inline-flex items-center gap-1">
                  {!hasSourceUrl(c) && (
                    <span
                      className="rounded border border-amber-500/30 px-1 text-[9px] leading-4 text-amber-300"
                      title={t('cases.noUrlTitle')}
                    >
                      {t('cases.noUrl')}
                    </span>
                  )}
                  {c.case_id}
                </span>
              </TableCell>
              <TableCell className="text-xs text-slate-400 whitespace-nowrap">{c.date_raw}</TableCell>
              <TableCell className="text-xs text-slate-300 max-w-[160px] truncate">
                <span className="inline-flex items-center gap-1">
                  {!hasCoords(c) && <MapPinOff className="h-3 w-3 text-slate-600 shrink-0" title={t('cases.noCoords')} />}
                  {locString(c)}
                </span>
              </TableCell>
              <TableCell className="max-w-[90px]">
                {agency && (
                  <Badge variant="outline" title={agency.label} className={cn('text-[10px] max-w-full truncate block', agency.badge)}>
                    {agency.label}
                  </Badge>
                )}
              </TableCell>
              <TableCell><Badge variant="outline" className={cn('text-[10px]', tierBadge(c.evidence_tier))}>{c.evidence_tier}</Badge></TableCell>
            </TableRow>
          )
        })}
      </TableBody>
    </Table>
  )
}
