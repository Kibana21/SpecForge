'use client'
import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { LayoutGrid, Plus, Search, Table2 } from 'lucide-react'
import { useProjects, useTriage, useViews } from '@/lib/hooks/useProjects'
import { AppShell } from '@/app/components/AppShell'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { ToggleGroup, ToggleGroupItem } from '@/app/components/ui/toggle-group'
import { UserMenu } from '@/app/components/UserMenu'
import { Skeleton } from '@/app/components/Skeleton'
import { EmptyState } from '@/app/components/EmptyState'
import { TriagePanel } from '@/app/components/portfolio/TriagePanel'
import { PortfolioTable } from '@/app/components/portfolio/PortfolioTable'
import { PortfolioBoard } from '@/app/components/portfolio/PortfolioBoard'
import { Layers } from 'lucide-react'

type Mode = 'table' | 'board'
const GROUP_OPTIONS = [
  { value: 'none', label: 'No grouping' },
  { value: 'business_unit', label: 'Business unit' },
  { value: 'status', label: 'Status' },
  { value: 'owner', label: 'Owner' },
]

export default function PortfolioPage() {
  const router = useRouter()
  const { views } = useViews()
  const { items: triage, computedAt, nextAt } = useTriage()

  const [view, setView] = useState('all')
  const [mode, setMode] = useState<Mode>('table')
  const [groupBy, setGroupBy] = useState('none')
  const [searchInput, setSearchInput] = useState('')
  const [debouncedQ, setDebouncedQ] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => setDebouncedQ(searchInput.trim()), 300)
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current) }
  }, [searchInput])

  const effectiveGroup = mode === 'table' ? groupBy : 'none'
  const { projects, groups, total, isLoading } = useProjects({ q: debouncedQ, view, group_by: effectiveGroup })

  return (
    <AppShell>
      <div className="flex flex-col h-full overflow-y-auto">
        {/* Hero */}
        <header className="shrink-0 relative overflow-hidden border-b border-[var(--border-default)] px-4 sm:px-6 py-5 sm:py-6">
          <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--accent-subtle)] to-transparent opacity-70" />
          <div className="relative flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
            <div className="min-w-0">
              <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-deep)]">Workspace</p>
              <h2 className="mt-1 text-xl sm:text-2xl font-bold text-[var(--text-primary)] tracking-tight">Project Portfolio</h2>
              <p className="mt-1 text-sm text-[var(--text-secondary)]">
                Track projects from intake to validated specs.
              </p>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <Button onClick={() => router.push('/projects/new')}>
                <Plus size={15} strokeWidth={2.5} />
                New Project
              </Button>
              <UserMenu />
            </div>
          </div>
        </header>

        <div className="flex-1 px-4 sm:px-6 py-5">
          <TriagePanel items={triage} computedAt={computedAt} nextAt={nextAt} />

          {/* Toolbar */}
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <ToggleGroup type="single" value={view} onValueChange={(v) => v && setView(v)} className="gap-1 flex-wrap">
              {views.map((v) => (
                <ToggleGroupItem key={v.view} value={v.view} size="sm" className="text-xs px-3 gap-1.5">
                  {v.label}
                  <span className="text-[10px] text-[var(--text-tertiary)]">{v.count}</span>
                </ToggleGroupItem>
              ))}
            </ToggleGroup>

            <div className="relative ml-auto flex-1 min-w-[180px] max-w-xs">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] z-10" />
              <Input
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                placeholder="Search by name, ID, or business unit…"
                className="h-9 pl-8 text-xs"
              />
            </div>

            {mode === 'table' && (
              <select
                value={groupBy}
                onChange={(e) => setGroupBy(e.target.value)}
                className="h-9 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 text-xs text-[var(--text-secondary)]"
              >
                {GROUP_OPTIONS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
              </select>
            )}

            <ToggleGroup type="single" value={mode} onValueChange={(v) => v && setMode(v as Mode)} className="gap-1">
              <ToggleGroupItem value="table" size="sm" className="px-2.5" aria-label="Table view"><Table2 size={15} /></ToggleGroupItem>
              <ToggleGroupItem value="board" size="sm" className="px-2.5" aria-label="Board view"><LayoutGrid size={15} /></ToggleGroupItem>
            </ToggleGroup>
          </div>

          {/* Body */}
          {isLoading ? (
            <Skeleton className="h-64 rounded-xl" />
          ) : groups ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {groups.map((g) => (
                <div key={g.key} className="card p-4">
                  <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{g.key}</p>
                  <p className="mt-1 text-2xl font-bold text-[var(--text-primary)]">{g.count}</p>
                  <div className="mt-2 flex gap-3 text-[11px] text-[var(--text-tertiary)]">
                    <span>{g.stale} stale</span><span>{g.review} review</span><span>{g.finalized} final</span>
                  </div>
                </div>
              ))}
            </div>
          ) : projects.length === 0 ? (
            <div className="rounded-2xl border-2 border-dashed border-[var(--border-default)] bg-[var(--bg-surface)]">
              <EmptyState
                icon={<Layers size={40} strokeWidth={1.2} className="text-[var(--accent)]" />}
                title={debouncedQ ? 'No matching projects' : 'No projects yet'}
                description={debouncedQ ? 'Try a different search or view.' : 'Create your first project to get started.'}
                action={<Button onClick={() => router.push('/projects/new')}><Plus size={14} />New Project</Button>}
              />
            </div>
          ) : (
            <>
              <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
                {total} {total === 1 ? 'project' : 'projects'}
              </p>
              {mode === 'table' ? <PortfolioTable projects={projects} /> : <PortfolioBoard projects={projects} />}
            </>
          )}
        </div>
      </div>
    </AppShell>
  )
}
