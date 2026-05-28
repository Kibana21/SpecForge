'use client'
/**
 * FRS Empty State — Stage 1 entry surface.
 *
 * Job:
 *   1. Communicate that this is a 2-stage pipeline (Modularize → Design)
 *   2. Show the 4-layer grounding (apps · docs · CB · BRD)
 *   3. Capture optional brief (with AI Enhance)
 *   4. Nudge upload of NFR/Architecture docs (non-blocking)
 *
 * Visual choreography:
 *   - ✦ icon: 2s breathing pulse (scale 1 → 1.04 → 1)
 *   - Source cards: staggered fade-up on mount (220ms ease-out, 50ms stagger)
 *   - CTA: disabled while readiness blocked; tooltip explains why
 */
import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import {
  Sparkles, BookOpen, FileText, Brain, ArrowRight, Loader2, Upload, Wand2, Check, AlertTriangle,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsBundleReadiness } from '@/lib/types'

interface Props {
  projectId: string
  readiness: FrsBundleReadiness | null | undefined
  /** Called after generation has been kicked off (transitions to S3 generation theater). */
  onGenerateStarted?: () => void
}

const EXAMPLE_BRIEFS = [
  'MVP for claims chatbot — focus on intake + triage flows',
  'Authentication + Notifications first; defer reporting to phase 2',
  'Vendor onboarding portal with KYC integration and document workflows',
] as const

export function FrsEmptyState({ projectId, readiness, onGenerateStarted }: Props) {
  const reduce = useReducedMotion()
  const [brief, setBrief] = useState('')
  const [enhancing, setEnhancing] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [placeholder] = useState(
    () => EXAMPLE_BRIEFS[Math.floor(Math.random() * EXAMPLE_BRIEFS.length)],
  )

  const canGenerate = Boolean(readiness?.can_generate) && !generating
  const blocking = readiness?.blocking_reason ?? null

  async function handleEnhance() {
    if (!brief.trim() || enhancing) return
    setEnhancing(true)
    try {
      const result = await api.frs.discoverEnhance(projectId, { brief: brief.trim() })
      setBrief(result.enhanced)
      toast.success('Brief enhanced')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Enhancement failed')
    } finally {
      setEnhancing(false)
    }
  }

  async function handleGenerate() {
    if (!canGenerate) return
    setGenerating(true)
    try {
      await api.frs.generate(projectId, { brief: brief.trim() || undefined })
      toast.success('Modularization started…')
      onGenerateStarted?.()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to start generation')
      setGenerating(false)
    }
  }

  const sourceCards = [
    {
      key: 'apps',
      icon: <Brain size={16} />,
      label: 'App Brain',
      description: 'Application facts & context',
      status: 'ready' as const,
    },
    {
      key: 'docs',
      icon: <FileText size={16} />,
      label: 'Documents',
      description: docsDescription(readiness),
      status: docsStatus(readiness),
    },
    {
      key: 'cb',
      icon: <Sparkles size={16} />,
      label: 'Concept Brief',
      description: cbDescription(readiness),
      status: cbStatus(readiness),
    },
    {
      key: 'brd',
      icon: <BookOpen size={16} />,
      label: 'BRD',
      description: brdDescription(readiness),
      status: brdStatus(readiness),
    },
  ]

  return (
    <div className="mx-auto max-w-3xl py-10 px-6">
      {/* ✦ hero icon */}
      <motion.div
        initial={reduce ? false : { opacity: 0, scale: 0.9 }}
        animate={
          reduce
            ? { opacity: 1 }
            : { opacity: 1, scale: [1, 1.04, 1] }
        }
        transition={
          reduce
            ? { duration: 0.2 }
            : {
                scale: { duration: 2, ease: 'easeInOut', repeat: Infinity },
                opacity: { duration: 0.4 },
              }
        }
        className="w-16 h-16 mx-auto rounded-full bg-amber-50 ring-1 ring-amber-200 flex items-center justify-center"
      >
        <Sparkles size={28} className="text-amber-600" />
      </motion.div>

      {/* Heading */}
      <h1 className="mt-6 text-center text-2xl font-semibold text-[var(--text-primary)]">
        Build the Functional Specifications
      </h1>
      <p className="mt-2 text-center text-sm text-[var(--text-secondary)] max-w-xl mx-auto leading-relaxed">
        Decompose your validated BRD into business-capability modules.<br />
        <span className="text-[var(--text-tertiary)]">
          Stage 1 of 2 — Stage 2 (per-module design) runs automatically after Stage 1 completes.
        </span>
      </p>

      {/* Grounding source cards */}
      <div className="mt-8">
        <p className="text-center text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-3">
          ⚡ Grounded in 4 sources
        </p>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {sourceCards.map((c, idx) => (
            <motion.div
              key={c.key}
              initial={reduce ? false : { opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut', delay: idx * 0.05 }}
              className={cn(
                'rounded-lg border bg-[var(--bg-surface)] px-3 py-2.5',
                'border-[var(--border-default)] hover:border-[var(--accent)]/30 transition-colors',
              )}
            >
              <div className="flex items-center gap-1.5 text-[var(--text-secondary)]">
                <span className="shrink-0" style={{ color: borderColorFor(c.key) }}>
                  {c.icon}
                </span>
                <span className="text-xs font-semibold text-[var(--text-primary)]">{c.label}</span>
              </div>
              <p className="mt-1 text-[10px] text-[var(--text-tertiary)] line-clamp-2 min-h-[26px]">
                {c.description}
              </p>
              <StatusPill status={c.status} />
            </motion.div>
          ))}
        </div>
      </div>

      {/* Brief textarea + AI Enhance */}
      <div className="mt-8 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
        <div className="flex items-center justify-between mb-2">
          <label htmlFor="frs-brief" className="text-xs font-semibold text-[var(--text-primary)]">
            Optional brief — what&apos;s the focus of this FRS bundle?
          </label>
          <button
            onClick={handleEnhance}
            disabled={!brief.trim() || enhancing}
            className="inline-flex items-center gap-1 text-[10px] text-[var(--accent)] hover:underline disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {enhancing ? (
              <Loader2 size={11} className="animate-spin" />
            ) : (
              <Wand2 size={11} />
            )}
            {enhancing ? 'Enhancing…' : '✦ AI Enhance'}
          </button>
        </div>
        <textarea
          id="frs-brief"
          rows={3}
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          placeholder={`e.g., "${placeholder}"`}
          className="w-full resize-none rounded-md border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)]"
        />
      </div>

      {/* NFR / Architecture upload hint (non-blocking) */}
      <div className="mt-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)]/50 px-3 py-2.5">
        <div className="flex items-start gap-2">
          <Upload size={13} className="text-[var(--text-tertiary)] mt-0.5 shrink-0" />
          <div className="flex-1 text-[11px] text-[var(--text-secondary)]">
            <span className="font-semibold">Recommended: upload NFR / Architecture docs.</span>{' '}
            <span className="text-[var(--text-tertiary)]">
              Files matching <span className="font-mono">nfr*</span>, <span className="font-mono">architecture*</span>,
              {' '}<span className="font-mono">technical-design*</span> ground the modularization.
            </span>
          </div>
        </div>
      </div>

      {/* CTA */}
      <div className="mt-8 flex flex-col items-center gap-2">
        <button
          onClick={handleGenerate}
          disabled={!canGenerate}
          className={cn(
            'inline-flex items-center gap-2 rounded-xl px-6 py-3 text-sm font-semibold transition-colors',
            canGenerate
              ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-hover)] shadow-[var(--shadow-card)]'
              : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] cursor-not-allowed',
          )}
          title={!canGenerate ? blocking ?? 'Not ready' : 'Start Stage 1 — Modularization'}
        >
          {generating ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <ArrowRight size={14} />
          )}
          {generating ? 'Starting…' : 'Discover & Modularize'}
        </button>
        {!canGenerate && blocking && (
          <p className="text-[11px] text-[var(--status-warning)] inline-flex items-center gap-1">
            <AlertTriangle size={11} /> {blocking}
          </p>
        )}
      </div>
    </div>
  )
}

// ── Helpers ─────────────────────────────────────────────────────────────────

type Status = 'ready' | 'pending' | 'missing'

function StatusPill({ status }: { status: Status }) {
  const styles: Record<Status, { label: string; cls: string; icon: JSX.Element }> = {
    ready: {
      label: 'Ready',
      cls: 'bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success-border)]',
      icon: <Check size={9} />,
    },
    pending: {
      label: 'Pending',
      cls: 'bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning-border)]',
      icon: <Loader2 size={9} className="animate-spin" />,
    },
    missing: {
      label: 'Missing',
      cls: 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)] border-[var(--border-default)]',
      icon: <AlertTriangle size={9} />,
    },
  }
  const s = styles[status]
  return (
    <span
      className={cn(
        'mt-2 inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[9px] font-medium',
        s.cls,
      )}
    >
      {s.icon} {s.label}
    </span>
  )
}

function docsDescription(r: FrsBundleReadiness | null | undefined): string {
  if (!r) return '—'
  if (r.docs_total_count === 0) return 'No project docs'
  if (r.docs_all_ready) return `${r.docs_ready_count} doc${r.docs_ready_count !== 1 ? 's' : ''} indexed`
  return `${r.docs_ready_count}/${r.docs_total_count} indexed`
}

function docsStatus(r: FrsBundleReadiness | null | undefined): Status {
  if (!r) return 'missing'
  if (r.docs_total_count === 0) return 'ready'
  if (r.docs_all_ready) return 'ready'
  return 'pending'
}

function cbDescription(r: FrsBundleReadiness | null | undefined): string {
  if (!r?.cb_status) return 'Not started'
  if (r.cb_status === 'validated') return 'Validated ✓'
  return r.cb_status.replace(/_/g, ' ')
}

function cbStatus(r: FrsBundleReadiness | null | undefined): Status {
  if (!r?.cb_ready) return 'missing'
  return 'ready'
}

function brdDescription(r: FrsBundleReadiness | null | undefined): string {
  if (!r?.brd_status) return 'Not started'
  if (r.brd_status === 'validated' && r.brd_summary) {
    return `${r.brd_summary.br_count} BRs · ${r.brd_summary.objective_count} obj · ${r.brd_summary.risk_count} risks`
  }
  return r.brd_status.replace(/_/g, ' ')
}

function brdStatus(r: FrsBundleReadiness | null | undefined): Status {
  if (!r?.brd_ready) return 'missing'
  return 'ready'
}

function borderColorFor(key: string): string {
  switch (key) {
    case 'apps': return '#0369A1'
    case 'docs': return '#0284C7'
    case 'cb':   return 'var(--accent)'
    case 'brd':  return '#DB2777'
    default:     return 'var(--text-tertiary)'
  }
}
