'use client'
import { useState } from 'react'
import { Sparkles, Building2, FileText, Loader2, CheckCircle2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import { DocReadinessPanel } from './DocReadinessPanel'
import type { BrdBundleReadiness } from '@/lib/types'

interface Props {
  projectId: string
  onStart: (context?: string) => void
  readiness: BrdBundleReadiness
  isLoading?: boolean
  appCount?: number
  cbReady?: boolean
}

export function BrdEmptyState({ onStart, readiness, isLoading, appCount = 0, cbReady }: Props) {
  const [context, setContext] = useState('')
  const [enhancing, setEnhancing] = useState(false)
  const [contextEnhanced, setContextEnhanced] = useState(false)

  const canGenerate = readiness.can_generate
  const docsCount = readiness.docs?.length ?? 0
  const hasPending = !readiness.docs_all_ready

  async function handleEnhance() {
    if (!context.trim() || enhancing) return
    setEnhancing(true)
    // Stub — in a real implementation, call api.brd.discoverEnhance
    await new Promise((r) => setTimeout(r, 800))
    setContextEnhanced(true)
    setEnhancing(false)
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center text-center gap-6 p-8 max-w-2xl mx-auto">
      {/* Icon */}
      <div className="w-20 h-20 rounded-2xl bg-[var(--accent-subtle)] flex items-center justify-center">
        <Sparkles size={40} className="text-[var(--accent)]" strokeWidth={1.2} />
      </div>

      {/* Title + description */}
      <div className="space-y-2">
        <h2 className="text-xl font-bold text-[var(--text-primary)]">Build the Business Requirements</h2>
        <p className="text-sm text-[var(--text-secondary)] max-w-md">
          SpecForge will synthesize a structured BRD from your Concept Brief, uploaded documents,
          and App Brain facts — grounded in your full project corpus.
        </p>
      </div>

      {/* Grounding badge */}
      {(appCount > 0 || docsCount > 0 || cbReady) && (
        <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
          {appCount > 0 && (
            <div className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-[var(--text-secondary)]">
              <Building2 size={13} className="text-[var(--accent)]" />
              <span>{appCount} app{appCount !== 1 ? 's' : ''}</span>
            </div>
          )}
          {docsCount > 0 && (
            <div className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-[var(--text-secondary)]">
              <FileText size={13} className="text-[var(--accent)]" />
              <span>{docsCount} document{docsCount !== 1 ? 's' : ''}</span>
            </div>
          )}
          {cbReady && (
            <div className="flex items-center gap-1.5 rounded-lg border border-[var(--status-success-border)] bg-[var(--status-success-bg)] px-3 py-2 text-[var(--status-success)]">
              <CheckCircle2 size={13} />
              <span>Concept Brief validated</span>
            </div>
          )}
        </div>
      )}

      {/* Context input */}
      <div className="w-full max-w-md text-left space-y-2">
        <div className="flex items-center justify-between">
          <label className="text-xs font-semibold text-[var(--text-secondary)]">
            Additional context{' '}
            <span className="font-normal text-[var(--text-tertiary)]">(optional)</span>
          </label>
          <button
            onClick={handleEnhance}
            disabled={enhancing || !context.trim()}
            className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-2 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:bg-[var(--accent-subtle)] hover:text-[var(--accent)] hover:border-[var(--accent-subtle)] transition-colors disabled:opacity-50"
          >
            {enhancing
              ? <><Loader2 size={10} className="animate-spin" /> Enhancing…</>
              : <><Sparkles size={10} /> AI Enhance</>}
          </button>
        </div>
        <textarea
          value={context}
          onChange={(e) => setContext(e.target.value)}
          rows={3}
          placeholder="Any specific focus areas, constraints, or emphasis for the BRD…"
          className="w-full resize-y rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)] focus:border-[var(--accent)]"
        />
        {contextEnhanced && (
          <div className="flex items-center gap-1.5 rounded-lg border border-[var(--accent-subtle)] bg-[var(--accent-subtle)] px-3 py-2 text-xs text-[var(--accent)]">
            <CheckCircle2 size={12} className="shrink-0" />
            Context enhanced with project grounding
          </div>
        )}
      </div>

      {/* Readiness panel (if docs are pending) */}
      {hasPending && (
        <div className="w-full max-w-md">
          <DocReadinessPanel readiness={readiness} />
        </div>
      )}

      {/* CTA */}
      <button
        onClick={() => onStart(context.trim() || undefined)}
        disabled={isLoading || !canGenerate}
        className={cn(
          'inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold transition-all',
          canGenerate && !isLoading
            ? 'bg-[var(--primary)] text-white hover:bg-[var(--primary-hover)] shadow-sm hover:shadow-md'
            : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] cursor-not-allowed',
        )}
        title={!canGenerate ? readiness.blocking_reason ?? 'Documents still indexing' : undefined}
      >
        {isLoading ? (
          <><Loader2 size={15} className="animate-spin" /> Starting…</>
        ) : (
          <><Sparkles size={15} /> Discover & Continue →</>
        )}
      </button>

      {!canGenerate && readiness.blocking_reason && (
        <p className="text-xs text-[var(--text-tertiary)] max-w-xs">{readiness.blocking_reason}</p>
      )}
    </div>
  )
}
