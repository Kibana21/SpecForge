'use client'
import { useState } from 'react'
import { toast } from 'sonner'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/app/components/ui/dialog'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { Textarea } from '@/app/components/ui/textarea'
import { Label } from '@/app/components/ui/label'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import { TC_TEST_TYPES, TC_PRIORITIES, TC_TYPE_STYLES } from '@/lib/testcases-manifest'
import type { TcTestType, TcPriority, TestCaseRow } from '@/lib/types'

interface Props {
  projectId: string
  testCase: TestCaseRow
  open: boolean
  onClose: () => void
  onSaved: () => void
}

export function TestCaseEditDialog({ projectId, testCase, open, onClose, onSaved }: Props) {
  const [title, setTitle] = useState(testCase.title)
  const [testType, setTestType] = useState<TcTestType>(testCase.test_type)
  const [priority, setPriority] = useState<TcPriority>(testCase.priority)
  const [given, setGiven] = useState(testCase.given)
  const [whenTxt, setWhenTxt] = useState(testCase.when)
  const [thenTxt, setThenTxt] = useState(testCase.then)
  const [assertions, setAssertions] = useState((testCase.key_assertions || []).join('\n'))
  const [expected, setExpected] = useState(testCase.expected_result)
  const [busy, setBusy] = useState(false)

  async function save() {
    const assertionList = assertions.split('\n').map(s => s.trim()).filter(Boolean)
    setBusy(true)
    try {
      await api.testcases.editRow(projectId, 'test_cases', testCase.id, {
        title, test_type: testType, priority, given, when: whenTxt, then: thenTxt,
        key_assertions: assertionList, expected_result: expected,
        viewports: testType === 'responsive' && testCase.viewports.length === 0
          ? ['mobile-360', 'tablet-768', 'desktop-1440'] : testCase.viewports,
      }, { expected_version: testCase.version })
      toast.success('Saved')
      onSaved()
      onClose()
    } catch (e: any) {
      if ((e?.message || '').includes('version_conflict')) toast.error('Edited elsewhere — reload and retry')
      else toast.error(e?.message || 'Save failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader><DialogTitle>Edit {testCase.row_key}</DialogTitle></DialogHeader>
        <div className="space-y-4">
          <div><Label>Title</Label><Input value={title} onChange={e => setTitle(e.target.value)} /></div>
          <div className="flex gap-6">
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
            <div>
              <Label>Priority</Label>
              <div className="flex gap-1 mt-1">
                {TC_PRIORITIES.map(p => (
                  <button key={p} type="button" onClick={() => setPriority(p)}
                    className={cn('rounded border px-2 py-1 text-[11px] font-medium',
                      priority === p ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent)]'
                        : 'border-[var(--border-default)] text-[var(--text-tertiary)]')}>{p}</button>
                ))}
              </div>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div><Label>Given</Label><Textarea rows={2} value={given} onChange={e => setGiven(e.target.value)} /></div>
            <div><Label>When</Label><Textarea rows={2} value={whenTxt} onChange={e => setWhenTxt(e.target.value)} /></div>
            <div><Label>Then</Label><Textarea rows={2} value={thenTxt} onChange={e => setThenTxt(e.target.value)} /></div>
          </div>
          <div><Label>Key assertions (one per line)</Label>
            <Textarea rows={3} value={assertions} onChange={e => setAssertions(e.target.value)} /></div>
          <div><Label>Expected result</Label>
            <Textarea rows={2} value={expected} onChange={e => setExpected(e.target.value)} /></div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose} disabled={busy}>Cancel</Button>
          <Button onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
