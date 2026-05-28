'use client'
/**
 * Stage A → Stage B continue banner.
 *
 * Appears at the bottom of the builder when Stage A is clean (no blocking
 * findings). Click triggers the Stage B kickoff (which will be wired in the
 * Stage B PRD; for v1 this just shows the celebratory transition).
 */
import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { ArrowRight, X } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { BrdConfettiBurst } from '@/app/components/brd/BrdConfettiBurst'

interface Props {
  moduleCount: number
  stubCount: number
  brCount: number
  /** Whether the banner is currently displayed. */
  open: boolean
  /** Called when the user clicks Continue (triggers Stage B). */
  onContinue: () => void
  /** Optional dismiss (sessionStorage-persisted by caller). */
  onDismiss?: () => void
}

export function FrsContinueStageBBanner({
  moduleCount, stubCount, brCount, open, onContinue, onDismiss,
}: Props) {
  const reduce = useReducedMotion()
  const [confettiActive, setConfettiActive] = useState(false)

  if (!open) return null

  function handleClick() {
    setConfettiActive(true)
    toast.success('Stage 1 approved — kicking off Stage 2…')
    setTimeout(() => {
      onContinue()
      setConfettiActive(false)
    }, 700)
  }

  return (
    <>
      <BrdConfettiBurst active={confettiActive} />
      <motion.div
        initial={reduce ? false : { y: 100, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={reduce ? undefined : { y: 100, opacity: 0 }}
        transition={{ duration: 0.28, ease: 'easeOut' }}
        className={cn(
          'fixed bottom-4 left-1/2 -translate-x-1/2 z-30',
          'w-full max-w-2xl px-4',
        )}
      >
        <div className="rounded-2xl border border-[var(--accent)]/30 bg-gradient-to-r from-[var(--accent-subtle)] to-emerald-50 shadow-[var(--shadow-md)] p-4">
          <div className="flex items-center gap-4">
            <div className="shrink-0 w-10 h-10 rounded-full bg-[var(--accent)] text-white flex items-center justify-center font-semibold">
              ✓
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-[var(--text-primary)]">
                Modularization complete · {moduleCount} module{moduleCount !== 1 ? 's' : ''} · {stubCount} backlog stub{stubCount !== 1 ? 's' : ''} · {brCount} BR{brCount !== 1 ? 's' : ''} covered
              </p>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Ready for Stage 2 — per-module FRS design. Estimated 60–120 s, runs in parallel.
              </p>
            </div>
            <button
              onClick={handleClick}
              className="shrink-0 inline-flex items-center gap-1.5 rounded-xl bg-[var(--accent)] text-white px-4 py-2 text-sm font-semibold hover:bg-[var(--accent-hover)] transition-colors shadow-[var(--shadow-sm)]"
            >
              Continue to Stage 2 <ArrowRight size={14} />
            </button>
            {onDismiss && (
              <button
                onClick={onDismiss}
                className="shrink-0 rounded-md p-1 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-elevated)] transition-colors"
                aria-label="Dismiss banner"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>
      </motion.div>
    </>
  )
}
