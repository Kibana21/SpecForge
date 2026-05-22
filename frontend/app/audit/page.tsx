'use client'
import { useEffect, useRef, useState } from 'react'
import { Download, Search, ShieldCheck } from 'lucide-react'
import { toast } from 'sonner'
import { AppShell } from '@/app/components/AppShell'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { ToggleGroup, ToggleGroupItem } from '@/app/components/ui/toggle-group'
import { Pagination } from '@/app/components/ui/Pagination'
import { Skeleton } from '@/app/components/Skeleton'
import { EmptyState } from '@/app/components/EmptyState'
import { StatTile } from '@/app/components/StatTile'
import { AuditTable } from '@/app/components/audit/AuditTable'
import { AuditDetailDialog } from '@/app/components/audit/AuditDetailDialog'
import { useAudit, useAuditSummary } from '@/lib/hooks/useAudit'
import { CATEGORY_TABS } from '@/lib/audit'
import { api } from '@/lib/api'
import type { AuditEventRead } from '@/lib/types'

const LIMIT = 50

export default function AuditLogPage() {
  const { summary } = useAuditSummary()

  const [category, setCategory] = useState('all')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [correlationId, setCorrelationId] = useState('')
  const [offset, setOffset] = useState(0)
  const [selected, setSelected] = useState<AuditEventRead | null>(null)
  const [exporting, setExporting] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(searchInput.trim()), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  // any filter change resets to the first page
  useEffect(() => { setOffset(0) }, [debouncedQ, category, start, end, correlationId])

  const filters = {
    q: debouncedQ || undefined,
    category,
    start: start || undefined,
    end: end ? `${end}T23:59:59` : undefined,
    correlation_id: correlationId || undefined,
    limit: LIMIT,
    offset,
  }
  const { events, total, isLoading } = useAudit(filters)

  async function handleExport() {
    setExporting(true)
    try {
      await api.audit.exportCsv(filters)
      toast.success('Audit log exported')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setExporting(false)
    }
  }

  function showRelated(cid: string) {
    setSelected(null)
    setCategory('all')
    setSearchInput('')
    setStart(''); setEnd('')
    setCorrelationId(cid)
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full overflow-y-auto">
        {/* Hero */}
        <header className="shrink-0 relative overflow-hidden border-b border-[var(--border-default)] px-4 sm:px-6 py-5 sm:py-6">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--accent-subtle)] to-transparent opacity-70" />
          <div className="relative flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-deep)]">Compliance</p>
              <h1 className="mt-1 flex items-center gap-2 text-xl sm:text-2xl font-bold tracking-tight text-[var(--text-primary)]">
                <ShieldCheck size={22} className="text-[var(--accent)]" /> Audit Log
              </h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                An immutable record of every consequential action — who did what, when, and to which artifact.
              </p>
            </div>
            <Button onClick={handleExport} disabled={exporting} variant="outline" className="shrink-0 self-start">
              <Download size={15} /> {exporting ? 'Exporting…' : 'Export CSV'}
            </Button>
          </div>

          {/* Security KPI tiles */}
          <div className="relative mt-5 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            <StatTile label="Events today" value={summary?.events_today ?? null} />
            <StatTile label="Failed logins (24h)" value={summary?.failed_logins_24h ?? null} tone="warning" />
            <StatTile label="Lockouts (24h)" value={summary?.lockouts_24h ?? null} tone="danger" />
            <StatTile label="Token reuse (7d)" value={summary?.token_reuse_7d ?? null} tone="danger" />
            <StatTile label="Deletions (7d)" value={summary?.deletions_7d ?? null} tone="warning" />
            <StatTile label="AI actions today" value={summary?.ai_actions_today ?? null} tone="info" />
          </div>
        </header>

        <div className="flex-1 px-4 sm:px-6 py-5">
          {/* Toolbar */}
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <ToggleGroup type="single" value={category} onValueChange={(v) => v && setCategory(v)} className="gap-1 flex-wrap">
              {CATEGORY_TABS.map((t) => (
                <ToggleGroupItem key={t.value} value={t.value} size="sm" className="text-xs px-3 gap-1.5">
                  <t.icon size={13} /> {t.label}
                </ToggleGroupItem>
              ))}
            </ToggleGroup>

            <div className="relative ml-auto flex-1 min-w-[200px] max-w-xs">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] z-10" />
              <Input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search event, actor, target…"
                className="h-9 pl-8 text-xs"
              />
            </div>
            <input type="date" value={start} onChange={(e) => setStart(e.target.value)} aria-label="From date"
              className="h-9 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 text-xs text-[var(--text-secondary)]" />
            <input type="date" value={end} onChange={(e) => setEnd(e.target.value)} aria-label="To date"
              className="h-9 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 text-xs text-[var(--text-secondary)]" />
          </div>

          {correlationId && (
            <div className="mb-3 flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <span>Filtered to correlation <code className="font-mono">{correlationId.slice(0, 12)}…</code></span>
              <button onClick={() => setCorrelationId('')} className="text-[var(--accent-deep)] hover:underline">clear</button>
            </div>
          )}

          {/* Body */}
          {isLoading ? (
            <Skeleton className="h-64 rounded-xl" />
          ) : events.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-[var(--border-default)] bg-[var(--bg-surface)]">
              <EmptyState
                icon={<ShieldCheck size={40} strokeWidth={1.2} className="text-[var(--accent)]" />}
                title="No matching events"
                description="Try a different category, search, or date range."
              />
            </div>
          ) : (
            <>
              <AuditTable events={events} onRowClick={setSelected} />
              <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
            </>
          )}
        </div>
      </div>

      <AuditDetailDialog event={selected} onClose={() => setSelected(null)} onShowRelated={showRelated} />
    </AppShell>
  )
}
