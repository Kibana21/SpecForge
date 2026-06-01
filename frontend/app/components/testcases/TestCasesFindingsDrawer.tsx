'use client'
import { ArrowRight, CheckCircle2, ChevronRight, Wrench, X } from 'lucide-react'
import { useMemo } from 'react'
import { cn } from '@/lib/utils'
import type { TestCasesFinding, TestCasesDetail } from '@/lib/types'

interface Props {
  open: boolean
  onClose: () => void
  findings: TestCasesFinding[] | null
  /** The current suites→plans→cases, used to turn row codes into real names. */
  detail?: TestCasesDetail | null
  /** Jump to the spec/plan a finding refers to (panel stays open). */
  onJump?: (rowKey: string) => void
  /** Run the auto-repair (clean up dangling refs + re-author thin specs). */
  onFix?: () => void
  busy?: boolean
}

/** Everyday-language description of each validator check — no jargon. */
const CHECK_HELP: Record<string, { label: string; what: string; auto?: boolean }> = {
  zero_plans: { label: 'No tests have been created yet', what: 'There’s nothing to check.' },
  plan_zero_cases: { label: 'A feature has no tests', what: 'A feature that needs testing doesn’t have a single test yet.', auto: true },
  must_br_untested: { label: 'A key business requirement isn’t fully tested', what: 'A “must-have” requirement still has parts that no test checks.' },
  scenario_uncovered: { label: 'A scenario has no test', what: 'Something the requirements say should happen isn’t checked by any test.', auto: true },
  fr_uncovered: { label: 'A requirement has no test', what: 'A requirement from the spec isn’t verified by any test yet.', auto: true },
  no_negative_test: { label: 'Missing a “what if it goes wrong” test', what: 'This feature should be tested for bad input or errors, but isn’t.', auto: true },
  orphan_case: { label: 'Test points at something that was removed', what: 'This test refers to a requirement that no longer exists.', auto: true },
  case_no_trace: { label: 'Test isn’t linked to a requirement', what: 'We can’t tell which business requirement this test is proving.', auto: true },
  responsive_no_viewports: { label: 'Screen-size test doesn’t say which sizes', what: 'A test meant to check different screen sizes doesn’t list any.', auto: true },
  case_not_rich: { label: 'Test doesn’t prove the result', what: 'It doesn’t spell out what should happen or what to check — so it can’t really confirm the feature works.', auto: true },
  business_rule_uncovered: { label: 'A business rule has no test', what: 'A rule from the spec isn’t exercised by any test.', auto: true },
  independent_test_uncovered: { label: 'No full walkthrough test', what: 'There’s no end-to-end test that walks through the whole feature.', auto: true },
  screen_no_responsive: { label: 'A screen isn’t checked on different sizes', what: 'No test checks this screen on mobile / tablet / desktop.' },
  plan_completeness: { label: 'A feature’s tests look unfinished', what: 'This feature’s test set isn’t fully fleshed out.' },
}

export function TestCasesFindingsDrawer({ open, onClose, findings, detail, onJump, onFix, busy }: Props) {
  // Build name lookups: case row_key → {test title, feature name, jump target}.
  const resolve = useMemo(() => {
    const caseByKey: Record<string, { title: string; spec: string }> = {}
    const specTitle: Record<string, string> = {}
    for (const s of detail?.suites ?? [])
      for (const p of s.plans ?? []) {
        specTitle[p.spec_row_key] = p.title || p.spec_row_key
        for (const c of p.cases ?? []) caseByKey[c.row_key] = { title: c.title || c.row_key, spec: p.spec_row_key }
      }
    return (rowKey: string): { name: string; feature: string | null } => {
      const c = caseByKey[rowKey]
      if (c) return { name: c.title, feature: specTitle[c.spec] || null }
      const spec = rowKey.startsWith('TP-') ? rowKey.replace(/-TC-\d+$/, '').slice(3) : rowKey
      return { name: specTitle[spec] || spec, feature: null }
    }
  }, [detail])

  const { mustFix, optional, mustCount, autoFixable } = useMemo(() => {
    const must: Record<string, TestCasesFinding[]> = {}
    const opt: Record<string, TestCasesFinding[]> = {}
    let mc = 0, af = 0
    for (const f of findings ?? []) {
      const blocking = f.group === 'critical' || f.group === 'major'
      ;(blocking ? must : opt)[f.check_id] ||= []
      ;(blocking ? must : opt)[f.check_id].push(f)
      if (blocking) mc++
      if (CHECK_HELP[f.check_id]?.auto) af++
    }
    return { mustFix: must, optional: opt, mustCount: mc, autoFixable: af }
  }, [findings])

  function Section({ groups, tone }: { groups: Record<string, TestCasesFinding[]>; tone: 'must' | 'opt' }) {
    const entries = Object.entries(groups)
    if (!entries.length) return null
    return (
      <div className="space-y-2">
        {entries.map(([check, list]) => {
          const help = CHECK_HELP[check] || { label: check, what: '' }
          return (
            <div key={check} className={cn('rounded-lg border px-3 py-2.5',
              tone === 'must' ? 'border-amber-300 bg-amber-50' : 'border-[var(--border-default)] bg-[var(--bg-elevated)]')}>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm font-semibold text-[var(--text-primary)]">{help.label}</span>
                <span className="shrink-0 rounded-full bg-white/80 px-2 py-0.5 text-[10px] font-medium text-[var(--text-secondary)]">
                  {list.length} test{list.length > 1 ? 's' : ''}
                </span>
              </div>
              {help.what && <div className="mt-0.5 text-xs text-[var(--text-secondary)]">{help.what}</div>}
              <div className="mt-2 space-y-1">
                {list.map((f, i) => {
                  const key = f.row_key || f.target_ref || ''
                  const r = resolve(key)
                  return (
                    <button key={i} onClick={() => onJump?.(key)}
                      title={onJump ? 'Open this test' : undefined}
                      className="group flex w-full min-w-0 flex-col gap-0.5 rounded-md bg-white/70 px-2 py-1.5 text-left hover:bg-white">
                      <span className="flex items-center gap-1">
                        <span className="min-w-0 flex-1 truncate text-xs text-[var(--text-primary)]">{r.name}</span>
                        <ChevronRight size={13} className="shrink-0 text-[var(--text-tertiary)] opacity-0 group-hover:opacity-100" />
                      </span>
                      {r.feature && <span className="truncate text-[10px] text-[var(--text-tertiary)]">in {r.feature}</span>}
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    )
  }

  if (!open) return null
  return (
    <aside className="absolute inset-y-0 right-0 z-30 flex w-full max-w-sm flex-col border-l border-[var(--border-default)] bg-[var(--bg-surface)] shadow-2xl">
      <header className="flex shrink-0 items-center justify-between gap-2 border-b border-[var(--border-default)] px-4 py-3">
        <h2 className="text-sm font-semibold text-[var(--text-primary)]">What needs fixing before sign-off?</h2>
        <button onClick={onClose} className="rounded p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]">
          <X size={16} />
        </button>
      </header>

      {!findings ? (
        <div className="flex-1 grid place-items-center text-sm text-[var(--text-tertiary)]">Checking the tests…</div>
      ) : findings.length === 0 ? (
        <div className="p-4">
          <div className="flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-3 text-sm font-semibold text-emerald-800">
            <CheckCircle2 size={16} /> Everything checks out — ready to approve. 🎉
          </div>
        </div>
      ) : (
        <>
          {/* Sticky summary + fix-all */}
          <div className="shrink-0 border-b border-[var(--border-default)] bg-[var(--bg-elevated)] px-4 py-3">
            <div className="text-sm text-[var(--text-secondary)]">
              <span className="font-bold text-[var(--text-primary)]">{mustCount}</span> item{mustCount !== 1 ? 's' : ''} to fix before this can be approved.
            </div>
            {onFix && autoFixable > 0 && (
              <button onClick={onFix} disabled={busy}
                className="mt-2 inline-flex w-full items-center justify-center gap-1 rounded-md bg-amber-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-600 disabled:opacity-60">
                <Wrench size={13} /> Fix {autoFixable} automatically <ArrowRight size={12} />
              </button>
            )}
            <div className="mt-1.5 text-[11px] text-[var(--text-tertiary)]">Click any test to open it. Locked &amp; manual tests are preserved.</div>
          </div>

          {/* Scrollable list */}
          <div className="flex-1 space-y-4 overflow-y-auto px-4 py-3">
            {mustCount > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-amber-700">Must fix before sign-off</div>
                <Section groups={mustFix} tone="must" />
              </div>
            )}
            {Object.keys(optional).length > 0 && (
              <div className="space-y-2">
                <div className="text-xs font-semibold uppercase tracking-wide text-[var(--text-tertiary)]">Nice to fix (won’t block sign-off)</div>
                <Section groups={optional} tone="opt" />
              </div>
            )}
          </div>
        </>
      )}
    </aside>
  )
}
