'use client'
import { useState, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Search, Boxes, Brain, Sparkles, Layers3 } from 'lucide-react'
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
import type { AppsFilter } from '@/lib/types'

type FilterTab = 'all' | '1' | '2' | '3' | 'mine'

export default function AppRegistryPage() {
  const router = useRouter()
  const [showModal, setShowModal] = useState(false)
  const [activeTab, setActiveTab] = useState<FilterTab>('all')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(searchInput), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [searchInput])

  const filters: AppsFilter = {
    q: debouncedQ || undefined,
    tier: activeTab === '1' ? 1 : activeTab === '2' ? 2 : activeTab === '3' ? 3 : undefined,
    mine: activeTab === 'mine',
  }

  const { data: apps, mutate, isLoading } = useApps(filters)

  const TABS: { key: FilterTab; label: string }[] = [
    { key: 'all', label: 'All' },
    { key: '1', label: 'Tier 1' },
    { key: '2', label: 'Tier 2' },
    { key: '3', label: 'Tier 3' },
    { key: 'mine', label: 'My Apps' },
  ]

  const totalApps = apps?.length ?? 0
  const brainReady = apps?.filter((a) => a.indexed_doc_count >= a.corpus_doc_count && a.corpus_doc_count > 0).length ?? 0
  const totalFacts = apps?.reduce((sum, a) => sum + (a.fact_count ?? 0), 0) ?? 0
  const onboarded = apps?.filter((a) => a.is_onboarded).length ?? 0

  return (
    <AppShell>
      <div className="flex flex-col h-full overflow-y-auto">
        {/* Hero header */}
        <header className="shrink-0 relative overflow-hidden border-b border-[var(--border-default)] px-6 py-6">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--accent-subtle)] to-transparent opacity-70" />
          <div className="relative flex items-start justify-between gap-4">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-deep)]">App Brain Library</p>
              <h1 className="mt-1 text-2xl font-bold tracking-tight text-[var(--text-primary)]">Application Registry</h1>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">Browse onboarded applications and their AI knowledge brains.</p>
            </div>
            <Button onClick={() => setShowModal(true)} className="shrink-0">
              <Plus size={15} strokeWidth={2.5} />
              New App
            </Button>
          </div>

          {/* Stat tiles */}
          <div className="relative mt-5 grid grid-cols-2 lg:grid-cols-4 gap-3">
            <StatTile icon={Boxes} label="Total apps" value={totalApps} tone="accent" />
            <StatTile icon={Brain} label="Brain ready" value={brainReady} tone="success" />
            <StatTile icon={Sparkles} label="Extracted facts" value={totalFacts} tone="info" />
            <StatTile icon={Layers3} label="Onboarded" value={onboarded} tone="warning" />
          </div>
        </header>

        {/* Filters */}
        <div className="shrink-0 flex items-center gap-3 px-6 py-3 border-b border-[var(--border-subtle)]">
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] z-10" />
            <Input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search apps…"
              className="h-9 pl-8 text-xs"
            />
          </div>
          <ToggleGroup
            type="single"
            value={activeTab}
            onValueChange={(v) => { if (v) setActiveTab(v as FilterTab) }}
            className="gap-1"
          >
            {TABS.map((tab) => (
              <ToggleGroupItem key={tab.key} value={tab.key} size="sm" className="text-xs px-3">
                {tab.label}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
        </div>

        {/* App grid */}
        <div className="flex-1 p-6">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-32 rounded-xl" />
              ))}
            </div>
          ) : apps && apps.length > 0 ? (
            <Stagger className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {apps.map((app) => (
                <StaggerItem key={app.id}>
                  <AppCard
                    app={app}
                    onClick={() => router.push(`/apps/${app.id}`)}
                  />
                </StaggerItem>
              ))}
            </Stagger>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-center py-20">
              <p className="text-sm text-[var(--text-secondary)] mb-1">No apps found</p>
              <p className="text-xs text-[var(--text-tertiary)]">
                {debouncedQ ? 'Try a different search term.' : 'Create your first app to get started.'}
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
