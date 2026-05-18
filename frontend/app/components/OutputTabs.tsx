'use client'
import clsx from 'clsx'
import type { SpecType } from '@/lib/types'
import { VersionBadge } from './VersionBadge'
import { Skeleton } from './Skeleton'

export type OutputTab = SpecType | 'gaps'

const TABS: { key: OutputTab; label: string }[] = [
  { key: 'functional', label: 'Functional' },
  { key: 'technical', label: 'Technical' },
  { key: 'user_stories', label: 'User Stories' },
  { key: 'review', label: 'Review' },
  { key: 'gaps', label: 'Open Questions' },
]

interface OutputTabsProps {
  activeTab: OutputTab
  onTabChange: (tab: OutputTab) => void
  loadingTabs: Partial<Record<OutputTab, boolean>>
  versionMap: Partial<Record<SpecType, number>>
}

export function OutputTabs({ activeTab, onTabChange, loadingTabs, versionMap }: OutputTabsProps) {
  return (
    <div className="flex items-center gap-1 px-4 py-3 border-b border-[var(--border-default)] overflow-x-auto scrollbar-hide">
      {TABS.map(({ key, label }) => {
        const isActive = activeTab === key
        const isLoading = loadingTabs[key]
        const version = key !== 'gaps' ? versionMap[key as SpecType] : undefined

        return (
          <button
            key={key}
            onClick={() => onTabChange(key)}
            className={clsx(
              'shrink-0 flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
              isActive
                ? 'bg-[var(--accent-blue)] text-white'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)]'
            )}
          >
            {isLoading ? (
              <Skeleton className="h-2 w-12 rounded" />
            ) : (
              <>
                {label}
                {version && version > 1 && (
                  <VersionBadge version={version} />
                )}
              </>
            )}
          </button>
        )
      })}
    </div>
  )
}
