'use client'

import { useEffect } from 'react'
import useSWR from 'swr'
import { X, History, GitBranch, Lock, User, Bot } from 'lucide-react'
import { apiFetch } from '@/lib/api'
import { useProjectContext } from '@/lib/context/ProjectContext'

interface VersionSnapshot {
  id: string
  document_key: string
  version_no: number
  actor_id: string | null
  created_at: string
  change_note: string | null
  change_count: number
  generation_type: 'ai' | 'human' | 'regeneration' | 'restore' | 'import'
  is_immutable: boolean
  changed_sections: Record<string, unknown> | null
}

function GenIcon({ type }: { type: VersionSnapshot['generation_type'] }) {
  if (type === 'ai' || type === 'regeneration') {
    return <Bot size={11} className="text-violet-500 shrink-0" />
  }
  return <User size={11} className="text-[var(--text-tertiary)] shrink-0" />
}

function genLabel(type: VersionSnapshot['generation_type']): string {
  return { ai: 'AI', human: 'Manual', regeneration: 'AI regen', restore: 'Restore', import: 'Import' }[type]
}

export function VersionHistoryPanel() {
  const { versionPanelOpen, activeDocumentKey, closeVersionPanel } = useProjectContext()

  const { data: versions, isLoading } = useSWR<VersionSnapshot[]>(
    versionPanelOpen && activeDocumentKey
      ? `/api/documents/${activeDocumentKey}/versions`
      : null,
    () => apiFetch<VersionSnapshot[]>(`/api/documents/${activeDocumentKey!}/versions`),
    { revalidateOnFocus: false }
  )

  // Close on Escape
  useEffect(() => {
    if (!versionPanelOpen) return
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') closeVersionPanel()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [versionPanelOpen, closeVersionPanel])

  if (!versionPanelOpen) return null

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/20 backdrop-blur-[1px]"
        onClick={closeVersionPanel}
      />

      {/* Panel */}
      <div className="fixed right-0 top-0 z-50 h-full w-80 bg-[var(--bg-surface)] border-l border-[var(--border-default)] shadow-xl flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-default)]">
          <div className="flex items-center gap-2">
            <History size={15} className="text-[var(--accent-blue)]" />
            <span className="text-sm font-semibold text-[var(--text-primary)]">Version History</span>
          </div>
          <button
            onClick={closeVersionPanel}
            className="p-1 rounded-md text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
            aria-label="Close version history"
          >
            <X size={14} />
          </button>
        </div>

        {/* Document key */}
        {activeDocumentKey && (
          <div className="px-4 py-2 border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-0.5">
              Document
            </p>
            <p className="text-xs font-mono text-[var(--text-secondary)] truncate">{activeDocumentKey}</p>
          </div>
        )}

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto">
          {isLoading ? (
            <div className="p-4 space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="h-16 rounded-lg bg-[var(--bg-elevated)] animate-pulse" />
              ))}
            </div>
          ) : !versions || versions.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full gap-3 px-6 text-center">
              <GitBranch size={32} strokeWidth={1.2} className="text-[var(--text-tertiary)]" />
              <p className="text-sm text-[var(--text-secondary)]">No versions yet</p>
              <p className="text-xs text-[var(--text-tertiary)]">
                Versions are created automatically when content is saved or generated.
              </p>
            </div>
          ) : (
            <div className="relative px-4 py-3">
              {/* Timeline spine */}
              <div className="absolute left-7 top-3 bottom-3 w-px bg-[var(--border-subtle)]" />

              <div className="space-y-2">
                {versions.map((v, idx) => (
                  <div key={v.id} className="relative flex gap-3">
                    {/* Dot */}
                    <div className="relative z-10 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--bg-surface)] border border-[var(--border-default)]">
                      {v.is_immutable ? (
                        <Lock size={9} className="text-amber-500" />
                      ) : (
                        <span className="text-[9px] font-bold text-[var(--text-tertiary)]">
                          {v.version_no}
                        </span>
                      )}
                    </div>

                    {/* Card */}
                    <div className="flex-1 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5 min-w-0">
                      <div className="flex items-center justify-between gap-1 mb-1">
                        <div className="flex items-center gap-1">
                          <GenIcon type={v.generation_type} />
                          <span className="text-[10px] font-semibold text-[var(--text-secondary)]">
                            v{v.version_no} · {genLabel(v.generation_type)}
                          </span>
                          {v.is_immutable && (
                            <span className="rounded-full bg-amber-100 px-1.5 py-0.5 text-[9px] font-semibold text-amber-700">
                              Locked
                            </span>
                          )}
                        </div>
                        {idx === 0 && (
                          <span className="rounded-full bg-[var(--accent-blue)] px-1.5 py-0.5 text-[9px] font-semibold text-white">
                            Current
                          </span>
                        )}
                      </div>
                      {v.change_note && (
                        <p className="text-[11px] text-[var(--text-secondary)] leading-relaxed line-clamp-2">
                          {v.change_note}
                        </p>
                      )}
                      <p className="text-[10px] text-[var(--text-tertiary)] mt-1">
                        {new Date(v.created_at).toLocaleString(undefined, {
                          month: 'short',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                        {v.change_count > 0 && ` · ${v.change_count} changes`}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  )
}
