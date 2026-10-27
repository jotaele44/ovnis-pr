import { useRef, useState } from 'react'
import { Activity, BarChart3, ClipboardCheck, List, Map as MapIcon, Menu } from 'lucide-react'
import {
  Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle,
} from '@/components/ui/sheet'
import { Button } from '@/components/ui/button'
import { useLocale } from '@/lib/locale'
import { cn } from '@/lib/utils'

// The persistent destinations. The spec caps the bottom bar at five, and "More"
// is the fifth, so at most four views live here; the rest go in the More sheet.
export const PRIMARY_VIEWS = [
  { id: 'cases', icon: List },
  { id: 'map', icon: MapIcon },
  { id: 'stats', icon: BarChart3 },
  { id: 'candidates', icon: ClipboardCheck },
]
export const MORE_VIEWS = [{ id: 'activity', icon: Activity }]

const itemClass =
  'flex min-h-[var(--bottom-nav-h)] flex-1 flex-col items-center justify-center gap-0.5 rounded-none px-1 text-[11px] font-medium leading-tight'

export default function MobileNav({ view, onChange, status }) {
  const { t } = useLocale()
  const [moreOpen, setMoreOpen] = useState(false)
  const moreRef = useRef(null)
  const moreActive = MORE_VIEWS.some((v) => v.id === view)
  return (
    <nav
      aria-label={t('nav.label')}
      className="flex shrink-0 border-t border-slate-800 bg-slate-900 pb-[var(--safe-bottom)] pl-[var(--safe-left)] pr-[var(--safe-right)]"
    >
      {PRIMARY_VIEWS.map(({ id, icon: Icon }) => (
        <Button
          key={id}
          type="button"
          variant="ghost"
          aria-current={view === id ? 'page' : undefined}
          onClick={() => onChange(id)}
          className={cn(itemClass, view === id ? 'text-primary' : 'text-slate-400')}
        >
          <Icon className="h-5 w-5" aria-hidden="true" />
          <span>{t(`nav.${id}`)}</span>
        </Button>
      ))}
      {/* Controlled rather than a SheetTrigger so the opener is an ordinary button
          with its own handler; focus is handed back to it on close below. */}
      <Button
        ref={moreRef}
        type="button"
        variant="ghost"
        aria-haspopup="dialog"
        aria-current={moreActive ? 'page' : undefined}
        onClick={() => setMoreOpen(true)}
        className={cn(itemClass, moreActive ? 'text-primary' : 'text-slate-400')}
      >
        <Menu className="h-5 w-5" aria-hidden="true" />
        <span>{t('nav.more')}</span>
      </Button>
      <Sheet open={moreOpen} onOpenChange={setMoreOpen}>
        <SheetContent
          side="bottom"
          onCloseAutoFocus={(e) => {
            e.preventDefault()
            moreRef.current?.focus()
          }}
          className="max-h-[85dvh] rounded-t-xl border-slate-800 bg-slate-950 pb-[calc(1.5rem+var(--safe-bottom))] text-slate-200"
        >
          <SheetHeader>
            <SheetTitle className="text-left text-slate-100">{t('nav.more')}</SheetTitle>
            <SheetDescription className="text-left text-slate-400">{t('nav.moreDescription')}</SheetDescription>
          </SheetHeader>
          <ul className="mt-4 grid gap-2">
            {MORE_VIEWS.map(({ id, icon: Icon }) => (
              <li key={id}>
                <Button
                  type="button"
                  variant="outline"
                  aria-current={view === id ? 'page' : undefined}
                  onClick={() => {
                    onChange(id)
                    setMoreOpen(false)
                  }}
                  className="h-12 w-full justify-start gap-3 border-slate-800 bg-slate-900 text-base"
                >
                  <Icon className="h-5 w-5" aria-hidden="true" />
                  {t(`nav.${id}`)}
                </Button>
              </li>
            ))}
          </ul>
          {status ? <p className="mt-4 text-sm text-slate-400">{status}</p> : null}
        </SheetContent>
      </Sheet>
    </nav>
  )
}
