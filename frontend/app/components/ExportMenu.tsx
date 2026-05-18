'use client'
import { useState, useRef, useEffect } from 'react'
import { Download, ChevronDown } from 'lucide-react'
import type { SpecType } from '@/lib/types'
import { api } from '@/lib/api'

const EXPORT_OPTIONS: { key: SpecType | 'all'; label: string }[] = [
  { key: 'functional', label: 'Functional Spec' },
  { key: 'technical', label: 'Technical Spec' },
  { key: 'user_stories', label: 'User Stories' },
  { key: 'review', label: 'Review' },
  { key: 'all', label: 'All (combined)' },
]

export function ExportMenu({ projectId }: { projectId: string }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handle(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [])

  function download(specType: string) {
    window.location.href = api.specs.exportUrl(projectId, specType)
    setOpen(false)
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:border-[var(--text-tertiary)] transition-colors"
      >
        <Download size={13} />
        Export
        <ChevronDown size={11} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1 z-20 w-44 rounded-xl border border-[var(--border-default)] bg-[var(--bg-elevated)] py-1 shadow-2xl">
          {EXPORT_OPTIONS.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => download(key)}
              className="flex w-full items-center gap-2 px-3 py-2 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-surface)] transition-colors"
            >
              <Download size={11} />
              {label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
