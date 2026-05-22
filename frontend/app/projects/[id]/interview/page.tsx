'use client'
import { useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, CheckCircle2, Send, Sparkles } from 'lucide-react'
import { toast } from 'sonner'
import { AppShell } from '@/app/components/AppShell'
import { Button } from '@/app/components/ui/button'
import { Badge } from '@/app/components/ui/badge'
import { Skeleton } from '@/app/components/Skeleton'
import { api } from '@/lib/api'
import { useUnderstanding } from '@/lib/hooks/useUnderstanding'
import type { Confidence, InterviewMessage } from '@/lib/types'

const CONF_VARIANT: Record<Confidence, 'success' | 'warning' | 'danger'> = {
  high: 'success', medium: 'warning', low: 'danger',
}

function asList(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
}

export default function InterviewPage() {
  const projectId = useParams().id as string
  const router = useRouter()
  const { detail, isLoading, mutate } = useUnderstanding(projectId)
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)

  const ru = detail?.understanding ?? null
  const messages = detail?.messages ?? []
  const generated = ru && ru.status !== 'draft'
  const validated = ru?.status === 'validated'
  const content = (ru?.content_json ?? {}) as Record<string, unknown>

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true)
    try { await fn(); await mutate(); toast.success(ok) }
    catch (e) { toast.error(e instanceof Error ? e.message : 'Failed') }
    finally { setBusy(false) }
  }

  const handleGenerate = () => run(() => api.projects.generateUnderstanding(projectId), 'Understanding generated')
  const handleValidate = () => run(async () => {
    await api.projects.validateUnderstanding(projectId)
    router.push(`/projects/${projectId}`)
  }, 'Understanding validated — generation unblocked')

  async function handleAnswer() {
    if (!answer.trim() || busy) return
    const a = answer.trim()
    setAnswer('')
    await run(() => api.projects.answerUnderstanding(projectId, a), 'Answer incorporated')
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full overflow-hidden">
        {/* Header */}
        <header className="shrink-0 flex items-center justify-between gap-3 border-b border-[var(--border-default)] px-4 sm:px-6 py-3">
          <div className="flex items-center gap-3 min-w-0">
            <button onClick={() => router.push(`/projects/${projectId}`)}
              className="shrink-0 p-1.5 rounded-lg text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)]" aria-label="Back">
              <ArrowLeft size={16} />
            </button>
            <div className="min-w-0">
              <h1 className="text-sm font-semibold text-[var(--text-primary)]">Requirement Understanding</h1>
              <p className="text-[11px] text-[var(--text-tertiary)]">
                {validated ? 'Validated' : generated ? 'In interview — answer open questions, then validate' : 'Not generated yet'}
              </p>
            </div>
          </div>
          {generated && !validated && (
            <Button onClick={handleValidate} disabled={busy}>
              <CheckCircle2 size={15} /> Validate Understanding
            </Button>
          )}
          {validated && <Badge variant="success">Validated</Badge>}
        </header>

        {isLoading ? (
          <div className="p-6"><Skeleton className="h-64 rounded-xl" /></div>
        ) : !generated ? (
          <div className="flex flex-1 flex-col items-center justify-center text-center gap-4 p-8">
            <Sparkles size={40} className="text-[var(--accent)]" strokeWidth={1.4} />
            <div>
              <p className="text-base font-semibold text-[var(--text-primary)]">Generate the Requirement Understanding</p>
              <p className="mt-1 text-sm text-[var(--text-secondary)] max-w-md">
                Synthesize a structured understanding from your sources and in-scope app brains.
              </p>
            </div>
            <Button onClick={handleGenerate} disabled={busy}><Sparkles size={15} /> Generate Understanding</Button>
          </div>
        ) : (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_minmax(0,380px)] overflow-hidden">
            {/* Thread + composer */}
            <div className="flex flex-col overflow-hidden border-r border-[var(--border-default)]">
              <div className="flex-1 overflow-y-auto p-4 space-y-3">
                {messages.map((m) => <Bubble key={m.id} m={m} />)}
              </div>
              <div className="shrink-0 border-t border-[var(--border-default)] p-3">
                <div className="flex items-end gap-2">
                  <textarea
                    value={answer}
                    onChange={(e) => setAnswer(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleAnswer() }}
                    placeholder="Answer an open question… (⌘+Enter to send)"
                    rows={2}
                    className="flex-1 resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
                  />
                  <Button onClick={handleAnswer} disabled={busy || !answer.trim()} className="h-9"><Send size={15} /></Button>
                </div>
              </div>
            </div>

            {/* Structured understanding panel */}
            <aside className="overflow-y-auto bg-[var(--bg-base)] p-4 space-y-4">
              <Field label="Objective" confidence={ru?.field_confidence?.objective?.confidence}>
                <p className="text-sm text-[var(--text-primary)]">{(content.objective as string) || '—'}</p>
              </Field>
              <ListField label="Stakeholders" items={asList(content.stakeholders)} fc={ru?.field_confidence?.stakeholders?.confidence} />
              <ListField label="Pain points" items={asList(content.pain_points)} fc={ru?.field_confidence?.pain_points?.confidence} />
              <ListField label="Functional areas" items={asList(content.functional_areas)} fc={ru?.field_confidence?.functional_areas?.confidence} />
              <ListField label="Systems" items={asList(content.systems)} fc={ru?.field_confidence?.systems?.confidence} />
              <ListField label="Integrations" items={asList(content.integrations)} fc={ru?.field_confidence?.integrations?.confidence} />
              <ListField label="Risks" items={asList(content.risks)} fc={ru?.field_confidence?.risks?.confidence} />
            </aside>
          </div>
        )}
      </div>
    </AppShell>
  )
}

function Bubble({ m }: { m: InterviewMessage }) {
  if (m.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-2xl rounded-br-sm bg-[var(--accent)] px-3 py-2 text-sm text-white">{m.content}</div>
      </div>
    )
  }
  const isQuestion = m.role === 'question'
  return (
    <div className="flex justify-start">
      <div className={`max-w-[85%] rounded-2xl rounded-bl-sm px-3 py-2 text-sm ${isQuestion ? 'bg-[var(--accent-subtle)] text-[var(--accent-deep)]' : 'bg-[var(--bg-surface)] border border-[var(--border-default)] text-[var(--text-primary)]'}`}>
        {isQuestion && <span className="mr-1 font-semibold">Q:</span>}
        {m.content}
        {m.citations?.length > 0 && (
          <div className="mt-1.5 flex flex-wrap gap-1">
            {m.citations.slice(0, 4).map((c, i) => (
              <span key={i} className="rounded border border-[var(--border-default)] bg-[var(--bg-base)] px-1.5 py-0.5 text-[10px] text-[var(--text-tertiary)]">
                {c.ref || c.doc_name || c.section_title || 'source'}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

function Field({ label, confidence, children }: { label: string; confidence?: Confidence; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">{label}</p>
        {confidence && <Badge variant={CONF_VARIANT[confidence]}>{confidence}</Badge>}
      </div>
      {children}
    </div>
  )
}

function ListField({ label, items, fc }: { label: string; items: string[]; fc?: Confidence }) {
  return (
    <Field label={label} confidence={fc}>
      {items.length === 0 ? (
        <p className="text-sm text-[var(--text-tertiary)]">—</p>
      ) : (
        <ul className="space-y-1">
          {items.map((it, i) => <li key={i} className="text-sm text-[var(--text-secondary)]">• {it}</li>)}
        </ul>
      )}
    </Field>
  )
}
