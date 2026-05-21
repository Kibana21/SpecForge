'use client'
import { useState, useCallback, useEffect, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Search } from 'lucide-react'
import { AppShell } from '@/app/components/AppShell'
import { AppCard } from '@/app/components/AppCard'
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

  return (
    <AppShell>
      <div className="flex flex-col h-full">
        {/* Top bar */}
        <header className="shrink-0 flex items-center justify-between px-6 py-4 border-b border-[var(--border-default)]">
          <h1 className="text-sm font-semibold text-[var(--text-primary)]">App Registry</h1>
          <button
            onClick={() => setShowModal(true)}
            className="flex items-center gap-1.5 rounded-lg bg-[var(--accent-blue)] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
          >
            <Plus size={13} />
            New App
          </button>
        </header>

        {/* Filters */}
        <div className="shrink-0 flex items-center gap-3 px-6 py-3 border-b border-[var(--border-subtle)]">
          <div className="relative flex-1 max-w-xs">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)]" />
            <input
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="Search apps…"
              className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] pl-8 pr-3 py-1.5 text-xs text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)]"
            />
          </div>
          <div className="flex items-center gap-1">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  activeTab === tab.key
                    ? 'bg-[var(--accent-blue)] text-white'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* App grid */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-32 rounded-xl" />
              ))}
            </div>
          ) : apps && apps.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-4">
              {apps.map((app) => (
                <AppCard
                  key={app.id}
                  app={app}
                  onClick={() => router.push(`/apps/${app.id}`)}
                />
              ))}
            </div>
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
