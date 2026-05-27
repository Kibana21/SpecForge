'use client'
import { useState } from 'react'
import { HelpCircle, Send, Loader2, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'

interface Message {
  id: string
  role: string
  content: string
  meta: Record<string, unknown>
  seq: number
}

interface SectionQuestionsProps {
  unitKey: string
  messages: Message[]
  projectId: string
  onAnswered: () => void
  onRegenerateUnit: (unitKey: string) => void
}

export function SectionQuestions({
  unitKey, messages, projectId, onAnswered, onRegenerateUnit,
}: SectionQuestionsProps) {
  const [expanded, setExpanded] = useState(true)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [regenerating, setRegenerating] = useState(false)

  // Questions for this unit
  const unitQuestions = messages.filter((m) => {
    const key = m.meta?.unit_key as string | undefined
    return key === unitKey && m.role === 'question'
  })
  if (unitQuestions.length === 0) return null

  // A question is "answered" if ANY user reply exists in the full thread with seq > q.seq.
  // User replies don't carry unit_key so we must check all messages, not just unit-keyed ones.
  const lastUserSeq = Math.max(
    ...messages.filter((m) => m.role === 'user').map((m) => m.seq),
    -1,
  )
  const openRaw = unitQuestions.filter((q) => q.seq > lastUserSeq)

  // Deduplicate by content — keep highest-seq copy to suppress repeated AI questions
  const seen = new Map<string, typeof openRaw[0]>()
  for (const q of openRaw) {
    const existing = seen.get(q.content)
    if (!existing || q.seq > existing.seq) seen.set(q.content, q)
  }
  const openQuestions = Array.from(seen.values()).sort((a, b) => a.seq - b.seq)

  if (openQuestions.length === 0) return null

  async function handleSubmit() {
    if (!answer.trim() || busy) return
    const a = answer.trim()
    setAnswer('')
    setBusy(true)
    try {
      await api.brd.answer(projectId, { answer: a })
      toast.success('Answer saved — section will refresh')
      onAnswered()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleRegenerate() {
    setRegenerating(true)
    try {
      await api.brd.regenerateUnit(projectId, unitKey)
      toast.success('Regenerating section…')
      onRegenerateUnit(unitKey)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Regeneration failed')
    } finally {
      setRegenerating(false)
    }
  }

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/60 overflow-hidden">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-amber-100/60 transition-colors"
      >
        <HelpCircle size={13} className="text-amber-600 shrink-0" />
        <span className="flex-1 text-xs font-semibold text-amber-800">
          {openQuestions.length} open question{openQuestions.length !== 1 ? 's' : ''} — answer to improve this section
        </span>
        {expanded ? <ChevronUp size={13} className="text-amber-500" /> : <ChevronDown size={13} className="text-amber-500" />}
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-3 border-t border-amber-200/60">
          <div className="pt-2 space-y-2">
            {openQuestions.map((q) => (
              <div key={q.id} className="rounded-lg border border-amber-200 bg-white/70 px-3 py-2">
                <p className="text-xs text-amber-900 leading-snug">{q.content}</p>
                {q.meta?.why != null && (
                  <p className="text-[10px] text-amber-600 italic mt-1">{String(q.meta.why as string)}</p>
                )}
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <p className="text-[11px] text-amber-700">
              Address any or all of the above in one reply — the AI will use your answer to regenerate this section.
            </p>
            <textarea
              rows={2}
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit() }}
              placeholder="Type your answer… (⌘+Enter to send)"
              disabled={busy}
              className="w-full resize-none rounded-lg border border-amber-200 bg-white/80 px-3 py-2 text-sm text-[var(--text-primary)] placeholder:text-[var(--text-tertiary)] focus:outline-none focus:ring-2 focus:ring-amber-300/50 disabled:opacity-50"
            />
            <div className="flex items-center gap-2">
              <button
                onClick={handleSubmit}
                disabled={busy || !answer.trim()}
                className="inline-flex items-center gap-1.5 rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 disabled:opacity-50 transition-colors"
              >
                {busy ? <Loader2 size={12} className="animate-spin" /> : <Send size={12} />}
                {busy ? 'Sending…' : 'Answer & refresh section'}
              </button>
              <button
                onClick={handleRegenerate}
                disabled={regenerating}
                title="Skip answering — regenerate with current context"
                className="inline-flex items-center gap-1.5 rounded-lg border border-amber-300 bg-amber-100 px-3 py-1.5 text-xs text-amber-800 hover:bg-amber-200 disabled:opacity-50 transition-colors"
              >
                <RefreshCw size={11} className={regenerating ? 'animate-spin' : ''} />
                {regenerating ? 'Regenerating…' : 'Regenerate section'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
