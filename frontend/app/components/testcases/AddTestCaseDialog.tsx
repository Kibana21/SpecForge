'use client'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/app/components/ui/dialog'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { Textarea } from '@/app/components/ui/textarea'
import { Label } from '@/app/components/ui/label'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { TC_TEST_TYPES, TC_TYPE_STYLES } from '@/lib/testcases-manifest'
import type { TcTestType, TestPlanRow } from '@/lib/types'

interface Props {
  projectId: string
  plan: TestPlanRow
  open: boolean
  onClose: () => void
  onAdded: () => void
}

/** Manual test case authoring with an FRS-element link picker + live coverage delta. */
export function AddTestCaseDialog({ projectId, plan, open, onClose, onAdded }: Props) {
  const [title, setTitle] = useState('')
  const [testType, setTestType] = useState<TcTestType>('functional')
  const [given, setGiven] = useState('')
  const [whenTxt, setWhenTxt] = useState('')
  const [thenTxt, setThenTxt] = useState('')
  const [assertions, setAssertions] = useState('')
  const [expected, setExpected] = useState('')
  const [links, setLinks] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)

  const targets = plan.coverage_targets || {}
  const scenarioKeys = targets.scenarios || []
  const frKeys = targets.frs || []
  const brKeys = targets.business_rules || []

  // Live coverage delta: which targeted elements would this case newly cover?
  const coveredNow = useMemo(() => {
    const set = new Set<string>()
    for (const c of plan.cases) {
      ;[...(c.scenario_refs || []), ...(c.fr_refs || []), ...(c.br_refs || [])].forEach(k => set.add(k))
    }
    return set
  }, [plan.cases])
  const allTargets = [...scenarioKeys, ...frKeys, ...brKeys]
  const beforePct = allTargets.length
    ? Math.round((allTargets.filter(k => coveredNow.has(k)).length / allTargets.length) * 100)
    : 100
  const afterPct = allTargets.length
    ? Math.round((allTargets.filter(k => coveredNow.has(k) || links.has(k)).length / allTargets.length) * 100)
    : 100

  function toggle(k: string) {
    setLinks(prev => {
      const next = new Set(prev)
      next.has(k) ? next.delete(k) : next.add(k)
      return next
    })
  }

  async function submit() {
    if (!title.trim()) { toast.error('Title is required'); return }
    const assertionList = assertions.split('\n').map(s => s.trim()).filter(Boolean)
    if (assertionList.length < 2) { toast.error('Add at least 2 key assertions (one per line)'); return }
    if (!expected.trim()) { toast.error('Expected result is required'); return }
    if (links.size === 0) { toast.error('Link to at least one FRS element'); return }
    setBusy(true)
    try {
      await api.testcases.addCase(projectId, plan.row_key, {
        title, test_type: testType, given, when: whenTxt, then: thenTxt,
        key_assertions: assertionList, expected_result: expected,
        viewports: testType === 'responsive' ? ['mobile-360', 'tablet-768', 'desktop-1440'] : [],
        priority: plan.priority,
        links: {
          scenario_refs: Array.from(links).filter(k => scenarioKeys.includes(k)),
          fr_refs: Array.from(links).filter(k => frKeys.includes(k)),
          br_refs: Array.from(links).filter(k => brKeys.includes(k)),
        },
      })
      toast.success('Test case added')
      onAdded()
      onClose()
    } catch (e: any) {
      toast.error(e?.message || 'Failed to add test case')
    } finally {
      setBusy(false)
    }
  }

  const LinkGroup = ({ label, keys }: { label: string; keys: string[] }) =>
    keys.length ? (
      <div>
        <div className="text-[11px] font-semibold text-[var(--text-tertiary)] mb-1">{label}</div>
        <div className="flex flex-wrap gap-1.5">
          {keys.map(k => (
            <button key={k} type="button" onClick={() => toggle(k)}
              className={cn('rounded border px-2 py-1 text-[11px] font-medium transition',
                links.has(k) ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]'
                  : coveredNow.has(k) ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : 'border-[var(--border-default)] hover:border-[var(--border-strong)]')}>
              {k}{coveredNow.has(k) && !links.has(k) ? ' ✓' : ''}
            </button>
          ))}
        </div>
      </div>
    ) : null

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Add test case to {plan.title}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div className="grid grid-cols-[1fr_auto] gap-3">
            <div>
              <Label>Title</Label>
              <Input value={title} onChange={e => setTitle(e.target.value)} placeholder="e.g. Reject zero amount" />
            </div>
            <div>
              <Label>Type</Label>
              <div className="flex flex-wrap gap-1 mt-1">
                {TC_TEST_TYPES.map(t => (
                  <button key={t} type="button" onClick={() => setTestType(t)}
                    className={cn('rounded border px-2 py-1 text-[11px] font-medium',
                      testType === t ? `${TC_TYPE_STYLES[t].bg} ${TC_TYPE_STYLES[t].text} ${TC_TYPE_STYLES[t].border}`
                        : 'border-[var(--border-default)] text-[var(--text-tertiary)]')}>
                    {TC_TYPE_STYLES[t].label}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div><Label>Given</Label><Textarea rows={2} value={given} onChange={e => setGiven(e.target.value)} /></div>
            <div><Label>When</Label><Textarea rows={2} value={whenTxt} onChange={e => setWhenTxt(e.target.value)} /></div>
            <div><Label>Then</Label><Textarea rows={2} value={thenTxt} onChange={e => setThenTxt(e.target.value)} /></div>
          </div>
          <div>
            <Label>Key assertions (one per line, ≥2)</Label>
            <Textarea rows={3} value={assertions} onChange={e => setAssertions(e.target.value)}
              placeholder={'Inline error shown on the field\nNo state change is persisted'} />
          </div>
          <div>
            <Label>Expected result</Label>
            <Textarea rows={2} value={expected} onChange={e => setExpected(e.target.value)}
              placeholder="Specific observable outcome (never 'works correctly')" />
          </div>
          <div className="rounded-lg border border-[var(--border-default)] p-3 space-y-3">
            <div className="flex items-center justify-between">
              <div className="text-xs font-semibold">Link to FRS elements <span className="text-red-500">*</span></div>
              {allTargets.length > 0 && (
                <div className="text-[11px] text-[var(--text-tertiary)]">
                  Plan coverage {beforePct}% {links.size > 0 && afterPct !== beforePct && (
                    <span className="text-[var(--accent)] font-semibold">→ {afterPct}%</span>
                  )}
                </div>
              )}
            </div>
            <LinkGroup label="Acceptance scenarios" keys={scenarioKeys} />
            <LinkGroup label="Functional requirements" keys={frKeys} />
            <LinkGroup label="Business rules" keys={brKeys} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={submit} disabled={busy}>{busy ? 'Adding…' : 'Add test case'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
