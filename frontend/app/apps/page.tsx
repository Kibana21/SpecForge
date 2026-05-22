'use client'
import { useState, useEffect, useMemo, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Search } from 'lucide-react'
import { AppShell } from '@/app/components/AppShell'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { ToggleGroup, ToggleGroupItem } from '@/app/components/ui/toggle-group'
import { Stagger, StaggerItem } from '@/app/components/motion/motion'
import { AppCard } from '@/app/components/AppCard'
import { StatTile } from '@/app/components/StatTile'
import { NewAppModal } from '@/app/components/NewAppModal'
import { Skeleton } from '@/app/components/Skeleton'
import { useApps } from '@/lib/hooks/useApps'
import { useAuth } from '@/lib/auth/AuthContext'

type FilterTab = 'all' | '1' | '2' | '3' | 'mine'

export default function AppRegistryPage() {
  const router = useRouter()
  const { user } = useAuth()
  const [showModal, setShowModal] = useState(false)
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(searchInput.trim().toLowerCase()), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchInput])

  // Fetch the full registry once; filter + count client-side.
  const { data: apps, mutate, isLoading } = useApps()

  // ── Aggregate stats (real where available, placeholders where not) ──────────
  const stats = useMemo(() => {
    const list = apps ?? []
    const onboarded = list.filter((a) => a.is_onboarded).length
    const totalFacts = list.reduce((s, a) => s + (a.fact_count ?? 0), 0)
    const totalDocs = list.reduce((s, a) => s + (a.corpus_doc_count ?? 0), 0)
    return { total: list.length, onboarded, totalFacts, totalDocs }
  }, [apps])

  // ── Tab counts ──────────────────────────────────────────────────────────────
  const counts = useMemo(() => {
    const list = apps ?? []
    return {
      all: list.length,
      '1': list.filter((a) => a.tier === 1).length,
      '2': list.filter((a) => a.tier === 2).length,
      '3': list.filter((a) => a.tier === 3).length,
      mine: list.filter((a) => a.owner_id && a.owner_id === user?.id).length,
    } as Record<FilterTab, number>
  }, [apps, user?.id])

  // ── Client-side filtering ─────────────────────────────────────────────────────
  const filtered = useMemo(() => {
    let list = apps ?? []
    if (activeTab === '1' || activeTab === '2' || activeTab === '3') {
      list = list.filter((a) => a.tier === Number(activeTab))
    } else if (activeTab === 'mine') {
      list = list.filter((a) => a.owner_id && a.owner_id === user?.id)
    }
    if (debouncedQ) {
      list = list.filter((a) =>
        [a.name, a.short_name, a.domain_area ?? '']
          .some((f) => f.toLowerCase().includes(debouncedQ)),
      )
    }
    return list
  }, [apps, activeTab, debouncedQ, user?.id])

  const TABS: { key: FilterTab; label: string }[] = [
    { key: 'all', label: 'All apps' },
    { key: '1', label: 'Tier 1' },
    { key: '2', label: 'Tier 2' },
    { key: '3', label: 'Tier 3' },
    { key: 'mine', label: 'Apps I own' },
  ]

  return (
    <AppShell>
      <div className="flex flex-col h-full overflow-y-auto">
        {/* Hero header */}
        <header className="shrink-0 relative overflow-hidden border-b border-[var(--border-default)] px-4 sm:px-6 py-5 sm:py-6">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--accent-subtle)] to-transparent opacity-70" />
          <div className="relative flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-deep)]">Org Library</p>
              <h1 className="mt-1 text-xl sm:text-2xl font-bold tracking-tight text-[var(--text-primary)]">Application Registry</h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">The organisation&apos;s grounded memory of its systems. Every app here feeds project documents with vetted facts, constraints, and skills.</p>
            </div>
            <Button onClick={() => setShowModal(true)} className="shrink-0 self-start">
              <Plus size={15} strokeWidth={2.5} />
              Onboard new app
            </Button>
          </div>

          {/* Stat tiles — real values + stylish placeholders for untracked metrics */}
          <div className="relative mt-5 grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatTile
              label="Apps onboarded"
              value={isLoading ? null : stats.onboarded}
              sublabel={`of ${stats.total} registered`}
              tone="success"
            />
            <StatTile
              label="Indexed facts"
              value={isLoading ? null : stats.totalFacts}
              sublabel={`across ${stats.totalDocs} docs`}
              tone="info"
            />
            <StatTile
              label="Active projects touching apps"
              value={null}
              sublabel="not tracked yet"
            />
            <StatTile
              label="Proposed updates"
              value={null}
              sublabel="awaiting owner review"
              tone="danger"
            />
          </div>
        </header>

        {/* Filters */}
        <div className="shrink-0 flex flex-wrap items-center gap-3 px-4 sm:px-6 py-3 border-b border-[var(--border-subtle)]">
          <ToggleGroup
            type="single"
            value={activeTab}
            onValueChange={(v) => { if (v) setActiveTab(v as FilterTab) }}
            className="gap-1"
          >
            {TABS.map((tab) => (
              <ToggleGroupItem key={tab.key} value={tab.key} size="sm" className="text-xs px-3 gap-1.5">
                {tab.label}
                <span className="text-[10px] text-[var(--text-tertiary)]">{counts[tab.key]}</span>
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <div className="relative ml-auto flex-1 min-w-[200px] max-w-xs">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] z-10" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search by app, owner, or area…"
              className="h-9 pl-8 text-xs"
            />
          </div>
        </div>

        {/* App grid */}
        <div className="flex-1 p-4 sm:p-6">
          {isLoading ? (
            <div className="grid grid-cols-[repeat(auto-fill,minmax(400px,1fr))] gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-36 rounded-xl" />
              ))}
            </div>
          ) : filtered.length > 0 ? (
            <Stagger className="grid grid-cols-[repeat(auto-fill,minmax(400px,1fr))] gap-4">
              {filtered.map((app) => (
                <StaggerItem key={app.id}>
                  <AppCard app={app} onClick={() => router.push(`/apps/${app.id}`)} />
                </StaggerItem>
              ))}
            </Stagger>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center py-20">
              <p className="text-sm text-[var(--text-secondary)] mb-1">No apps found</p>
              <p className="text-xs text-[var(--text-tertiary)]">
                {debouncedQ ? 'Try a different search term.' : 'Onboard your first app to get started.'}
              </p>
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <NewAppModal
          onClose={() => setShowModal(false)}
          onCreated={() => { setShowModal(false); mutate() }}
        />
      )}
    </AppShell>
  )
}
