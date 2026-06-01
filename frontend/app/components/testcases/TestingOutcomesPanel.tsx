'use client'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog'
import { ArrowRight, Info, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'
import { TC_TYPE_STYLES } from '@/lib/testcases-manifest'
import type { TestCasesCoverage, TcTestType } from '@/lib/types'

interface Props {
  coverage: TestCasesCoverage | null
  open: boolean
  onClose: () => void
  onFillGaps?: () => void
}

const TYPE_HELP: Record<string, string> = {
  functional: 'happy-path behaviour works',
  integration: 'parts work together',
  e2e: 'whole journey works end-to-end',
  negative: 'bad input is rejected',
  edge_case: 'boundary / unusual cases',
  responsive: 'UI works on all screen sizes',
}

function statusColor(pct: number) {
  if (pct >= 100) return 'text-emerald-600'
  if (pct >= 80) return 'text-amber-600'
  return 'text-red-600'
}

/**
 * Testing outcomes — explains, per module, WHAT the test suite proves: which
 * business requirements it verifies, how well it covers failure paths, and the
 * mix of test types. Plain-language, newcomer-friendly.
 */
export function TestingOutcomesPanel({ coverage, open, onClose, onFillGaps }: Props) {
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>What do these tests actually prove?</DialogTitle></DialogHeader>

        {!coverage ? (
          <div className="py-12 text-center text-sm text-[var(--text-tertiary)]">Loading…</div>
        ) : (
          <div className="space-y-4">
            <div className="flex gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-2.5 text-xs text-[var(--text-secondary)]">
              <Info size={15} className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" />
              <div>
                For each module this shows the <b>business requirements its tests verify</b>, how thoroughly
                it tests <b>things going wrong</b> (negative &amp; edge cases — not just the happy path), and
                the <b>mix of test types</b>. Use it to spot modules that are only lightly tested.
              </div>
            </div>

            <div className="flex items-baseline gap-2">
              <span className={cn('text-2xl font-bold', statusColor(coverage.project_pct))}>{coverage.project_pct}%</span>
              <span className="text-xs text-[var(--text-secondary)]">
                of spec items covered overall · {coverage.summary.must_br_tested}/{coverage.summary.must_br_total} must-have requirements verified
              </span>
            </div>

            {coverage.modules.map(m => {
              const o = m.outcomes || ({} as any)
              const dist: Record<string, number> = o.type_distribution || {}
              const neg = o.risk_coverage?.negative ?? 0
              const edge = o.risk_coverage?.edge ?? 0
              const uncovered: string[] = o.uncovered_outcomes || []
              const totalCases = Object.values(dist).reduce((a, b) => a + b, 0) || 1
              return (
                <div key={m.module_row_key} className="rounded-lg border border-[var(--border-default)] p-3 space-y-2.5">
                  <div className="flex items-center justify-between">
                    <div className="font-semibold text-sm">{m.title}</div>
                    <div className={cn('text-xs font-semibold', statusColor(m.pct))}>{m.pct}% covered · {m.case_count} cases</div>
                  </div>

                  {/* Requirements verified */}
                  {(o.outcomes_proven?.length ?? 0) > 0 && (
                    <div className="flex flex-wrap items-center gap-1 text-xs">
                      <ShieldCheck size={13} className="text-emerald-600" />
                      <span className="text-[var(--text-tertiary)]">Verifies:</span>
                      {o.outcomes_proven.map((b: string) => (
                        <span key={b} className="rounded bg-emerald-50 px-1.5 py-0.5 text-[10px] font-medium text-emerald-700">{b}</span>
                      ))}
                    </div>
                  )}

                  {/* Failure-path testing, in plain words */}
                  <div className="text-[11px] text-[var(--text-secondary)]">
                    <span className="text-[var(--text-tertiary)]">Tests for things going wrong: </span>
                    <span className="font-medium text-red-600">{neg} rejection</span> +
                    <span className="font-medium text-amber-600"> {edge} edge-case</span> test{neg + edge !== 1 ? 's' : ''}
                    {neg + edge === 0 && <span className="text-red-600"> — none yet ⚠</span>}
                  </div>

                  {/* Test mix as a single labelled bar */}
                  <div>
                    <div className="flex h-2 w-full overflow-hidden rounded-full bg-[var(--bg-sunken)]">
                      {(Object.keys(dist) as TcTestType[]).map(t => (
                        <div key={t} className={cn('h-full', TC_TYPE_STYLES[t]?.bg, 'border-r border-white')}
                          style={{ width: `${(dist[t] / totalCases) * 100}%` }} title={`${TC_TYPE_STYLES[t]?.label}: ${dist[t]}`} />
                      ))}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-0.5">
                      {(Object.keys(dist) as TcTestType[]).map(t => (
                        <span key={t} className="text-[10px] text-[var(--text-tertiary)]">
                          <span className={cn('inline-block w-2 h-2 rounded-sm align-middle mr-1', TC_TYPE_STYLES[t]?.bg)} />
                          {TC_TYPE_STYLES[t]?.label} {dist[t]} <span className="opacity-70">— {TYPE_HELP[t]}</span>
                        </span>
                      ))}
                    </div>
                  </div>

                  {uncovered.length > 0 && (
                    <div className="text-[11px] text-amber-700">
                      ⚠ {uncovered.length} spec item{uncovered.length > 1 ? 's' : ''} in this module still have no test.
                    </div>
                  )}
                </div>
              )
            })}

            {onFillGaps && coverage.summary.covered < coverage.summary.total_elements && (
              <button onClick={onFillGaps}
                className="inline-flex items-center gap-1 rounded-md bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600">
                Fill the untested items automatically <ArrowRight size={12} />
              </button>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}
