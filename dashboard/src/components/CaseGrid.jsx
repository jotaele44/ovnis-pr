import { useMemo, useState } from 'react'
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import {
  Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
} from '@/components/ui/select'
import { tierBadge } from '@/lib/format'
import { confidenceTone, locString, hasCoords } from '@/lib/prufon-format'
import { cn } from '@/lib/utils'
import { MapPinOff } from 'lucide-react'

// All 470 master cases (includes the ~106 without coordinates, flagged inline).
export default function CaseGrid({ cases = [], selectedId, onSelect }) {
  const [decade, setDecade] = useState('all')
  const [tier, setTier] = useState('all')
  const [q, setQ] = useState('')

  const decades = useMemo(
    () => ['all', ...Array.from(new Set(cases.map((c) => c.decade).filter(Boolean))).sort()],
    [cases],
  )

  const rows = cases.filter((c) =>
    (decade === 'all' || c.decade === decade) &&
    (tier === 'all' || c.evidence_tier === tier) &&
    (!q || (c.description || '').toLowerCase().includes(q.toLowerCase()) || locString(c).toLowerCase().includes(q.toLowerCase())))

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 p-2">
        <span className="text-xs text-slate-400 shrink-0 w-10">{rows.length}</span>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search…" className="h-7 flex-1 text-xs bg-slate-950 border-slate-800" />
        <Select value={decade} onValueChange={setDecade}>
          <SelectTrigger className="h-7 w-[100px] text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>{decades.map((d) => <SelectItem key={d} value={d} className="text-xs">{d === 'all' ? 'All decades' : d}</SelectItem>)}</SelectContent>
        </Select>
        <Select value={tier} onValueChange={setTier}>
          <SelectTrigger className="h-7 w-[90px] text-xs"><SelectValue /></SelectTrigger>
          <SelectContent>{['all', 'T1', 'T2', 'T3', 'T4'].map((t) => <SelectItem key={t} value={t} className="text-xs">{t === 'all' ? 'All tiers' : t}</SelectItem>)}</SelectContent>
        </Select>
      </div>
      <div className="flex-1 overflow-auto">
        <Table>
          <TableHeader className="sticky top-0 bg-slate-900 z-10">
            <TableRow className="hover:bg-transparent border-slate-800">
              <TableHead className="text-slate-400">Case</TableHead>
              <TableHead className="text-slate-400">Date</TableHead>
              <TableHead className="text-slate-400">Location</TableHead>
              <TableHead className="text-slate-400">Tier</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((c) => (
              <TableRow
                key={c.case_id}
                onClick={() => onSelect?.(c)}
                className={cn('cursor-pointer border-slate-800', selectedId === c.case_id ? 'bg-violet-500/10' : 'hover:bg-slate-800/50')}
              >
                <TableCell className="text-xs text-slate-200 whitespace-nowrap">{c.case_id}</TableCell>
                <TableCell className="text-xs text-slate-400 whitespace-nowrap">{c.date_raw}</TableCell>
                <TableCell className="text-xs text-slate-300 max-w-[160px] truncate">
                  <span className="inline-flex items-center gap-1">
                    {!hasCoords(c) && <MapPinOff className="h-3 w-3 text-slate-600 shrink-0" title="no coordinates" />}
                    {locString(c)}
                  </span>
                </TableCell>
                <TableCell><Badge variant="outline" className={cn('text-[10px]', tierBadge(c.evidence_tier))}>{c.evidence_tier}</Badge></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
