'use client'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog'
import { AlertTriangle, ArrowRight, CheckCircle2, Info } from 'lucide-react'
import { useMemo } from 'react'
import { cn } from '@/lib/utils'
import type { TestCasesCoverage } from '@/lib/types'

interface Props {
  coverage: TestCasesCoverage | null
  open: boolean
  onClose: () => void
  onFillGaps?: () => void
}

/** A status pill from a coverage %: fully / partly / not tested. */
function pill(pct: number) {
  if (pct >= 100) return { label: 'Fully tested', cls: 'bg-emerald-100 text-emerald-700' }
  if (pct > 0) return { label: 'Partly tested', cls: 'bg-amber-100 text-amber-700' }
  return { label: 'Not tested', cls: 'bg-red-100 text-red-700' }
}

function Dot({ color }: { color: string }) {
  return <span className={cn('inline-block w-2 h-2 rounded-full', color)} />
}

/**
 * Coverage chain — shows, in plain language, whether the test suite covers what the
 * business asked for, tracing Business requirement → Functional spec → Test plan.
 */
export function TestCasesCoverageGalaxy({ coverage, open, onClose, onFillGaps }: Props) {
  // spec_row_key → human title (for turning codes into names in the alert/columns)
  const specTitle = useMemo(() => {
    const m: Record<string, string> = {}
    for (const mod of coverage?.modules ?? [])
      for (const sp of mod.specs) m[sp.spec_row_key] = sp.title
    return m
  }, [coverage])
  const name = (k: string) => specTitle[k] || k

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Are we testing what the business asked for?</DialogTitle>
        </DialogHeader>

        {!coverage ? (
          <div className="py-12 text-center text-sm text-[var(--text-tertiary)]">Loading coverage…</div>
        ) : (
          <div className="space-y-5">
            {/* Plain-language explainer */}
            <div className="flex gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-2.5 text-xs text-[var(--text-secondary)]">
              <Info size={15} className="mt-0.5 shrink-0 text-[var(--text-tertiary)]" />
              <div>
                This follows the chain from <b>business requirements</b> → the <b>functional specs</b> that
                build them → the <b>test plans</b> that verify them. A requirement counts as
                <b> fully tested only when every spec that implements it is 100% covered</b>.
                “Must-have” requirements are the ones flagged critical in the BRD.
              </div>
            </div>

            {/* Headline + legend */}
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-baseline gap-2">
                <span className="text-3xl font-bold text-[var(--text-primary)]">
                  {coverage.summary.must_br_tested}<span className="text-[var(--text-tertiary)] text-lg">/{coverage.summary.must_br_total}</span>
                </span>
                <span className="text-sm text-[var(--text-secondary)]">must-have requirements fully tested
                  <span className="text-[var(--text-tertiary)]"> · {coverage.summary.covered}/{coverage.summary.total_elements} spec items covered ({coverage.project_pct}%)</span>
                </span>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-[var(--text-tertiary)]">
                <span className="flex items-center gap-1"><Dot color="bg-emerald-500" /> Fully tested</span>
                <span className="flex items-center gap-1"><Dot color="bg-amber-400" /> Partly tested</span>
                <span className="flex items-center gap-1"><Dot color="bg-red-500" /> Not tested</span>
              </div>
            </div>

            {/* What still needs work (plain language, real names) */}
            {coverage.summary.must_br_untested > 0 ? (
              <div className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2.5">
                <div className="flex items-center gap-2 text-sm font-semibold text-amber-800">
                  <AlertTriangle size={15} />
                  {coverage.summary.must_br_untested} must-have requirement{coverage.summary.must_br_untested > 1 ? 's' : ''} still have gaps
                </div>
                <ul className="mt-1.5 space-y-1 text-xs text-amber-800">
                  {coverage.brd_chain.filter(b => !b.tested).map(b => {
                    const specs = b.implementing_specs.filter(s => {
                      const sp = coverage.modules.flatMap(m => m.specs).find(x => x.spec_row_key === s)
                      return !sp || sp.pct < 100
                    })
                    return (
                      <li key={b.br_row_key}>
                        <span className="font-semibold">{b.title || b.br_row_key}</span>
                        <span className="font-mono text-[10px] opacity-70"> ({b.br_row_key})</span>
                        {specs.length
                          ? <> — needs more tests in: {specs.map(name).join(', ')}</>
                          : <> — no functional spec implements it yet</>}
                      </li>
                    )
                  })}
                </ul>
                {onFillGaps && (
                  <button onClick={onFillGaps}
                    className="mt-2 inline-flex items-center gap-1 rounded-md bg-amber-500 px-2.5 py-1 text-xs font-semibold text-white hover:bg-amber-600">
                    Fill these gaps automatically <ArrowRight size={12} />
                  </button>
                )}
              </div>
            ) : (
              <div className="flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2.5 text-sm font-semibold text-emerald-800">
                <CheckCircle2 size={15} /> Every must-have requirement is fully tested.
              </div>
            )}

            {/* The 3-step chain */}
            <div className="grid grid-cols-3 gap-3 text-xs">
              <ColHeader step="1" title="Business requirements" sub="what the business needs (must-haves)" />
              <ColHeader step="2" title="Functional specs" sub="how each requirement is built" />
              <ColHeader step="3" title="Test plans" sub="the tests that verify them" />

              {/* Col 1 — BRs */}
              <div className="space-y-1.5">
                {coverage.brd_chain.length === 0 && <Empty>No must-have requirements</Empty>}
                {coverage.brd_chain.map(b => (
                  <div key={b.br_row_key}
                    className={cn('rounded-lg border px-2.5 py-2',
                      b.tested ? 'border-emerald-200 bg-emerald-50/60' : 'border-red-300 bg-red-50/60')}>
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-semibold text-[var(--text-primary)] leading-tight">{b.title || b.br_row_key}</span>
                      <StatusChip ok={b.tested} okLabel="Tested" badLabel="Has gaps" />
                    </div>
                    <div className="mt-0.5 text-[10px] text-[var(--text-tertiary)]">
                      <span className="font-mono">{b.br_row_key}</span> · built by {b.implementing_specs.length} spec{b.implementing_specs.length !== 1 ? 's' : ''}
                    </div>
                  </div>
                ))}
              </div>

              {/* Col 2 — Specs */}
              <div className="space-y-1.5">
                {coverage.modules.flatMap(m => m.specs).map(s => {
                  const p = pill(s.pct)
                  return (
                    <div key={s.spec_row_key}
                      className={cn('rounded-lg border px-2.5 py-2',
                        s.pct >= 100 ? 'border-emerald-200 bg-emerald-50/50'
                          : s.pct > 0 ? 'border-amber-300 bg-amber-50/50' : 'border-red-300 bg-red-50/50')}>
                      <div className="font-semibold text-[var(--text-primary)] leading-tight">{s.title}</div>
                      <div className="mt-0.5 flex items-center justify-between">
                        <span className="font-mono text-[10px] text-[var(--text-tertiary)]">{s.spec_row_key} · {s.priority}</span>
                        <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', p.cls)}>{s.pct}% · {p.label}</span>
                      </div>
                    </div>
                  )
                })}
              </div>

              {/* Col 3 — Test plans (by module) */}
              <div className="space-y-1.5">
                {coverage.modules.map(m => {
                  const p = pill(m.pct)
                  return (
                    <div key={m.module_row_key} className="rounded-lg border border-[var(--border-default)] px-2.5 py-2">
                      <div className="font-semibold text-[var(--text-primary)] leading-tight">{m.title}</div>
                      <div className="mt-0.5 flex items-center justify-between">
                        <span className="text-[10px] text-[var(--text-tertiary)]">{m.plan_count} plans · {m.case_count} cases</span>
                        <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium', p.cls)}>{m.pct}%</span>
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}

function ColHeader({ step, title, sub }: { step: string; title: string; sub: string }) {
  return (
    <div className="pb-1 border-b border-[var(--border-subtle)]">
      <div className="flex items-center gap-1.5">
        <span className="grid place-items-center w-4 h-4 rounded-full bg-[var(--accent)] text-white text-[9px] font-bold">{step}</span>
        <span className="text-[11px] font-semibold uppercase tracking-wide text-[var(--text-secondary)]">{title}</span>
      </div>
      <div className="mt-0.5 text-[10px] text-[var(--text-tertiary)] normal-case">{sub}</div>
    </div>
  )
}

function StatusChip({ ok, okLabel, badLabel }: { ok: boolean; okLabel: string; badLabel: string }) {
  return (
    <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium',
      ok ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700')}>
      {ok ? okLabel : badLabel}
    </span>
  )
}

function Empty({ children }: { children: React.ReactNode }) {
  return <div className="text-[var(--text-tertiary)] text-[11px] py-2">{children}</div>
}
