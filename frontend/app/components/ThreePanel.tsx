'use client'
import { useState } from 'react'
import clsx from 'clsx'

interface ThreePanelProps {
  left: React.ReactNode
  center: React.ReactNode
  right: React.ReactNode
}

type MobileTab = 'docs' | 'spec' | 'notes'

export function ThreePanel({ left, center, right }: ThreePanelProps) {
  const [mobileTab, setMobileTab] = useState<MobileTab>('spec')

  return (
    <>
      {/* Mobile segmented tabs */}
      <div className="md:hidden sticky top-0 z-10 bg-[var(--bg-surface)] border-b border-[var(--border-default)] px-3 py-2">
        <div className="flex gap-1 bg-[var(--bg-elevated)] rounded-lg p-0.5">
          {(['docs', 'spec', 'notes'] as MobileTab[]).map((tab) => (
            <button
              key={tab}
              onClick={() => setMobileTab(tab)}
              className={clsx(
                'flex-1 py-1.5 text-xs font-semibold rounded-md capitalize transition-colors',
                mobileTab === tab
                  ? 'bg-[var(--bg-surface)] text-[var(--text-primary)] shadow-sm'
                  : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              )}
            >
              {tab}
            </button>
          ))}
        </div>
      </div>

      {/* Mobile panels */}
      <div className="md:hidden overflow-y-auto h-[calc(100vh-112px)]">
        {mobileTab === 'docs'  && left}
        {mobileTab === 'spec'  && center}
        {mobileTab === 'notes' && right}
      </div>

      {/* Desktop three-column grid */}
      <div className="hidden md:grid grid-cols-[minmax(0,20%)_minmax(0,55%)_minmax(0,25%)] h-[calc(100vh-56px)]">
        <div className="overflow-y-auto border-r border-[var(--border-default)] bg-[var(--bg-base)]">{left}</div>
        <div className="overflow-y-auto border-r border-[var(--border-default)] bg-[var(--bg-surface)]">{center}</div>
        <div className="overflow-y-auto bg-[var(--bg-base)]">{right}</div>
      </div>
    </>
  )
}
