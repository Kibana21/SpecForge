'use client'
import { useMemo } from 'react'
import { CheckCircle2, Loader2, AlertTriangle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { BRD_UNITS } from '@/lib/brd-manifest'

interface Props {
  unitStatus: Record<string, { completeness: number; confidence: string }> | null
  currentUnit: string | null
}

type NodeState = 'done' | 'current' | 'queued' | 'error'

// Semantic pipeline stages — maps naturally to what the BRD sections mean
const PIPELINE_STAGES = [
  {
    label: 'Foundation',
    keys: ['business_context', 'problem_statement'],
  },
  {
    label: 'Structure',
    keys: ['objectives', 'stakeholders', 'actors', 'scope'],
  },
  {
    label: 'Processes',
    keys: ['asis_process', 'tobe_process'],
  },
  {
    label: 'Requirements',
    keys: ['business_requirements'],
    keystone: true,
  },
  {
    label: 'Analysis',
    keys: ['data_entities', 'assumptions', 'constraints', 'dependencies', 'kpis'],
  },
  {
    label: 'Synthesis',
    keys: ['risks', 'report_requirements', 'implementation_phases', 'decisions'],
  },
  {
    label: 'Closing',
    keys: ['open_questions', 'milestones', 'references', 'glossary'],
  },
] as const

function getNodeState(
  key: string,
  unitStatus: Record<string, { completeness: number; confidence: string }> | null,
  currentUnit: string | null,
): NodeState {
  if (!unitStatus) return 'queued'
  if (unitStatus[`_error_${key}`]) return 'error'
  const us = unitStatus[key]
  if (us && us.completeness > 0) return 'done'
  if (key === currentUnit) return 'current'
  return 'queued'
}

function StageChip({
  unit, state, keystone,
}: {
  unit: { key: string; label: string }
  state: NodeState
  keystone?: boolean
}) {
  return (
    <div
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all duration-300',
        keystone && 'px-4 py-2 text-sm font-semibold rounded-xl',
        state === 'done' && 'border-[var(--status-success-border)] bg-[var(--status-success-bg)] text-[var(--status-success)]',
        state === 'current' && 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent-deep)] shadow-sm ring-2 ring-[var(--accent)]/20',
        state === 'error' && 'border-[var(--status-danger-border)] bg-[var(--status-danger-bg)] text-[var(--status-danger)]',
        state === 'queued' && 'border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-tertiary)]',
      )}
    >
      {state === 'done' && <CheckCircle2 size={12} className="shrink-0" />}
      {state === 'current' && (
        <span className="relative shrink-0 flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-[var(--accent)] opacity-75" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-[var(--accent)]" />
        </span>
      )}
      {state === 'error' && <AlertTriangle size={12} className="shrink-0" />}
      {state === 'queued' && (
        <span className="shrink-0 w-2 h-2 rounded-full border border-[var(--border-strong)]" />
      )}
      <span>{unit.label}</span>
    </div>
  )
}

export function UnitDagViz({ unitStatus, currentUnit }: Props) {
  const doneCount = useMemo(
    () => BRD_UNITS.filter((u) => getNodeState(u.key, unitStatus, currentUnit) === 'done').length,
    [unitStatus, currentUnit],
  )

  const unitMap = useMemo(() => {
    const m: Record<string, { key: string; label: string }> = {}
    BRD_UNITS.forEach((u) => { m[u.key] = u })
    return m
  }, [])

  // Which stage is currently active?
  const activeStageIdx = useMemo(() => {
    if (!currentUnit) return -1
    return PIPELINE_STAGES.findIndex((s) => (s.keys as readonly string[]).includes(currentUnit))
  }, [currentUnit])

  return (
    <div className="flex flex-1 flex-col items-center justify-center p-8 overflow-y-auto">
      {/* Icon + title */}
      <div className="w-14 h-14 rounded-2xl bg-[var(--accent-subtle)] flex items-center justify-center mb-4">
        <Loader2 size={26} className="text-[var(--accent)] animate-spin" strokeWidth={1.5} />
      </div>
      <p className="text-base font-semibold text-[var(--text-primary)] text-center">
        Building Business Requirements Document
      </p>
      <p className="mt-1 text-sm text-[var(--text-tertiary)] text-center">
        {currentUnit
          ? `Right now: writing ${BRD_UNITS.find((u) => u.key === currentUnit)?.label ?? currentUnit}…`
          : doneCount === BRD_UNITS.length
          ? 'All sections complete — finishing up…'
          : `${doneCount} of ${BRD_UNITS.length} sections complete`}
      </p>

      {/* Progress bar */}
      <div className="w-full max-w-xs h-1 rounded-full bg-[var(--bg-sunken)] mt-4 mb-8">
        <div
          className="h-1 rounded-full bg-[var(--accent)] transition-[width] duration-700"
          style={{ width: `${Math.max(2, (doneCount / BRD_UNITS.length) * 100)}%` }}
        />
      </div>

      {/* Pipeline stages */}
      <div className="w-full max-w-lg flex flex-col items-center gap-0">
        {PIPELINE_STAGES.map((stage, stageIdx) => {
          const isActive = stageIdx === activeStageIdx
          const stageUnits = stage.keys.map((k) => unitMap[k]).filter(Boolean)
          const stageStates = stageUnits.map((u) => getNodeState(u.key, unitStatus, currentUnit))
          const allDone = stageStates.every((s) => s === 'done')
          const hasActive = stageStates.some((s) => s === 'current')

          return (
            <div key={stage.label} className="flex flex-col items-center w-full">
              {/* Stage row */}
              <div
                className={cn(
                  'w-full flex flex-col items-center gap-2 rounded-2xl px-4 py-3 transition-all duration-300',
                  isActive && 'bg-[var(--accent-subtle)]/30',
                )}
              >
                {/* Stage label */}
                <div className="flex items-center gap-2">
                  <span
                    className={cn(
                      'text-[10px] font-semibold uppercase tracking-widest',
                      allDone ? 'text-[var(--status-success)]' :
                      hasActive ? 'text-[var(--accent)]' :
                      'text-[var(--text-tertiary)]',
                    )}
                  >
                    {stage.label}
                  </span>
                  {allDone && (
                    <CheckCircle2 size={11} className="text-[var(--status-success)]" />
                  )}
                </div>
                {/* Chips row */}
                <div className="flex flex-wrap justify-center gap-2">
                  {stageUnits.map((unit) => (
                    <StageChip
                      key={unit.key}
                      unit={unit}
                      state={getNodeState(unit.key, unitStatus, currentUnit)}
                      keystone={'keystone' in stage && stage.keystone}
                    />
                  ))}
                </div>
              </div>

              {/* Connector arrow between stages */}
              {stageIdx < PIPELINE_STAGES.length - 1 && (
                <div className="flex flex-col items-center my-0.5">
                  <div className={cn(
                    'w-px h-4',
                    allDone ? 'bg-[var(--status-success-border)]' : 'bg-[var(--border-default)]',
                  )} />
                  <svg width="8" height="5" viewBox="0 0 8 5" fill="none" className={cn(
                    allDone ? 'text-[var(--status-success-border)]' : 'text-[var(--border-default)]',
                  )}>
                    <path d="M0 0L4 5L8 0" stroke="currentColor" strokeWidth="1.5" />
                  </svg>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
