'use client'
/**
 * ProjectChatPanel — conversation + reasoning trail for the Project Copilot.
 * Forked from AskPanel with three key changes:
 *   1. Endpoint → /api/projects/{id}/ask (no mode/top_k)
 *   2. Answer rendered via ProjectMarkdown (inline S:/C:/F: chips)
 *   3. Reasoning trail streamed as ReAct tool calls, trace drives EvidencePanel
 */
import { useState, useRef, useEffect, useCallback } from 'react'
import {
  Send, Check, Loader2, Plus, MessageSquare,
  History, Trash2, ChevronRight, Sparkles, ChevronDown, ChevronUp,
} from 'lucide-react'
import { motion, AnimatePresence, useReducedMotion } from 'framer-motion'
import { AskTraceDrawer } from './AskTraceDrawer'
import { StarterChips } from './StarterChips'
import { ProjectMarkdown } from '@/lib/inlineTokens'
import { api, authedFetch } from '@/lib/api'
import type {
  CitationItem, AskSessionListItem, AskSessionMessage, ProjectAskTrace, DeepTrace,
} from '@/lib/types'

interface Props {
  projectId: string
  onTrace: (trace: ProjectAskTrace | null) => void
  hoverToken: string | null
  onHoverToken: (token: string | null) => void
}

interface Step {
  text: string
  at: number   // ms since the question was asked, for elapsed-time traceability
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  steps?: Step[]
  citations?: CitationItem[]
  trace?: ProjectAskTrace
  streaming?: boolean
  stepsOpen?: boolean
}

const MAX_HISTORY_TURNS = 8

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const m = Math.floor(diff / 60000)
  if (m < 1) return 'just now'
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

export function ProjectChatPanel({ projectId, onTrace, hoverToken, onHoverToken }: Props) {
  const reduced = useReducedMotion()
  const [question, setQuestion] = useState('')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<AskSessionListItem[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [traceOpen, setTraceOpen] = useState<DeepTrace | null>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const sessionIdRef = useRef<string | null>(null)

  const loadSessions = useCallback(async () => {
    try { setSessions(await api.projects.listChatSessions(projectId)) } catch { /* ignore */ }
  }, [projectId])

  useEffect(() => { loadSessions() }, [loadSessions])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  function updateLastAssistant(fn: (m: ChatMessage) => ChatMessage) {
    setMessages((prev) => {
      const next = [...prev]
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === 'assistant') { next[i] = fn(next[i]); break }
      }
      return next
    })
  }

  async function persist(msgs: ChatMessage[]) {
    if (msgs.length < 2) return
    const compact: AskSessionMessage[] = msgs.map((m) => ({
      role: m.role,
      content: m.content,
      mode: undefined,
      ...(m.role === 'assistant'
        ? {
            citations: (m.citations ?? []).map((c) => ({ id: c.id, doc_name: c.doc_name, chunk_no: c.chunk_no })),
            trace: m.trace as unknown as import('@/lib/types').DeepTrace,
          }
        : {}),
    }))
    const title = (msgs.find((m) => m.role === 'user')?.content ?? 'Chat').slice(0, 80)
    try {
      const res = await api.projects.saveChatSession(projectId, { id: sessionIdRef.current, title, messages: compact })
      sessionIdRef.current = res.id
      loadSessions()
    } catch { /* non-fatal */ }
  }

  async function handleAsk(q?: string) {
    const text = (q ?? question).trim()
    if (!text || isStreaming) return

    const history = messages.slice(-MAX_HISTORY_TURNS).map((m) => ({ role: m.role, content: m.content }))
    setMessages((prev) => [
      ...prev,
      { role: 'user', content: text },
      { role: 'assistant', content: '', steps: [], citations: [], streaming: true, stepsOpen: true },
    ])
    setQuestion('')
    setError(null)
    setIsStreaming(true)
    const askStart = Date.now()

    try {
      const res = await authedFetch(`/api/projects/${projectId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: text, history }),
      })
      if (!res.ok || !res.body) {
        setError('Request failed'); updateLastAssistant((m) => ({ ...m, streaming: false })); setIsStreaming(false); return
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'step')
              updateLastAssistant((m) => ({ ...m, steps: [...(m.steps ?? []), { text: event.text, at: Date.now() - askStart }] }))
            if (event.type === 'chunk')
              updateLastAssistant((m) => ({ ...m, content: m.content + event.text }))
            if (event.type === 'trace') {
              updateLastAssistant((m) => ({ ...m, trace: event.trace }))
              onTrace(event.trace)
            }
            if (event.type === 'citations')
              updateLastAssistant((m) => ({ ...m, citations: event.citations }))
            if (event.type === 'error')
              setError(event.message)
            if (event.type === 'done')
              updateLastAssistant((m) => ({ ...m, streaming: false, stepsOpen: false }))
          } catch { /* ignore malformed */ }
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      updateLastAssistant((m) => ({ ...m, streaming: false }))
      setIsStreaming(false)
      setMessages((prev) => { void persist(prev); return prev })
    }
  }

  function newChat() {
    setMessages([]); setError(null); sessionIdRef.current = null; setShowHistory(false)
    onTrace(null)
  }

  async function replaySession(sid: string) {
    try {
      const data = await api.projects.getChatSession(projectId, sid)
      const msgs: ChatMessage[] = data.messages.map((m) => ({
        role: m.role,
        content: m.content,
        citations: (m.citations ?? []).map((c) => ({ ...c, text_excerpt: '' })),
        trace: m.trace as unknown as ProjectAskTrace,
        streaming: false,
      }))
      setMessages(msgs)
      sessionIdRef.current = data.id
      setShowHistory(false)
      setError(null)
      const lastTrace = msgs.filter((m) => m.trace).pop()?.trace
      if (lastTrace) onTrace(lastTrace)
    } catch {
      setError('Could not load that session')
    }
  }

  async function removeSession(sid: string, e: React.MouseEvent) {
    e.stopPropagation()
    try {
      await api.projects.deleteChatSession(projectId, sid)
      if (sessionIdRef.current === sid) newChat()
      loadSessions()
    } catch { /* ignore */ }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk() }
  }

  const groundedCount = (msg: ChatMessage) => {
    const t = msg.trace
    if (!t) return 0
    return (t.sections?.length ?? 0) + (t.selected_concepts?.length ?? 0) + ((t.facts?.length) ?? 0)
  }

  return (
    <div className="flex flex-col h-full gap-3 min-h-0">
      {/* Top bar */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <p className="text-sm font-semibold text-[var(--text-primary)] flex-1">Ask the Project</p>

        {/* History */}
        <div className="relative">
          <button
            onClick={() => setShowHistory((s) => !s)}
            className={`flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md transition-colors ${
              showHistory ? 'bg-[var(--bg-elevated)] text-[var(--text-secondary)]' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
            }`}
          >
            <History size={12} /> History{sessions.length ? ` (${sessions.length})` : ''}
          </button>
          {showHistory && (
            <div className="absolute right-0 z-20 mt-1 w-72 max-h-80 overflow-y-auto rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-lg p-1">
              {sessions.length === 0 ? (
                <p className="text-[11px] text-[var(--text-tertiary)] px-3 py-3 text-center">No saved chats yet.</p>
              ) : sessions.map((s) => (
                <div
                  key={s.id}
                  onClick={() => replaySession(s.id)}
                  className="group flex items-center gap-2 px-2.5 py-2 rounded-md hover:bg-[var(--bg-elevated)] cursor-pointer"
                >
                  <MessageSquare size={12} className="text-[var(--text-tertiary)] flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-[var(--text-primary)] truncate">{s.title}</p>
                    <p className="text-[10px] text-[var(--text-tertiary)]">{s.message_count} msgs · {relativeTime(s.updated_at)}</p>
                  </div>
                  <button
                    onClick={(e) => removeSession(s.id, e)}
                    className="opacity-0 group-hover:opacity-100 text-[var(--text-tertiary)] hover:text-red-500 flex-shrink-0"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {messages.length > 0 && (
          <button
            onClick={newChat}
            disabled={isStreaming}
            className="flex items-center gap-1.5 text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] disabled:opacity-50"
          >
            <Plus size={12} /> New chat
          </button>
        )}
      </div>

      {/* Thread */}
      {messages.length > 0 ? (
        <div ref={threadRef} className="flex flex-col gap-3 flex-1 overflow-y-auto min-h-0 pr-1">
          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} className="self-end max-w-[85%] rounded-lg rounded-br-sm bg-[var(--accent)] text-white px-3 py-2 text-sm whitespace-pre-wrap">
                {m.content}
              </div>
            ) : (
              <div key={i} className="self-start w-full space-y-1.5">
                {/* Reasoning trail */}
                {m.steps && m.steps.length > 0 && (
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] overflow-hidden">
                    <button
                      onClick={() => setMessages((prev) => prev.map((msg, j) =>
                        j === i ? { ...msg, stepsOpen: !msg.stepsOpen } : msg))}
                      className="w-full flex items-center gap-2 px-3 py-2 text-[11px] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
                    >
                      {m.streaming && !m.content ? (
                        <Loader2 size={11} className="animate-spin text-[var(--accent)] flex-shrink-0" />
                      ) : (
                        <Check size={11} className="text-emerald-500 flex-shrink-0" />
                      )}
                      <span className="flex-1 text-left">
                        {m.stepsOpen ? 'Reasoning' : `${m.steps.length} step${m.steps.length !== 1 ? 's' : ''} completed`}
                      </span>
                      {m.stepsOpen ? <ChevronUp size={11} /> : <ChevronDown size={11} />}
                    </button>
                    {m.stepsOpen && (
                      <div className="px-3 pb-2 space-y-1.5 border-t border-[var(--border-subtle)]">
                        <AnimatePresence initial={false}>
                          {m.steps.map((s, si) => {
                            const pending = m.streaming && si === m.steps!.length - 1 && !m.content
                            return (
                              <motion.div
                                key={si}
                                initial={reduced ? undefined : { opacity: 0, x: -4 }}
                                animate={{ opacity: 1, x: 0 }}
                                className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)]"
                              >
                                {pending
                                  ? <Loader2 size={11} className="animate-spin text-[var(--accent)] flex-shrink-0" />
                                  : <Check size={11} className="text-emerald-500 flex-shrink-0" />}
                                <span className="flex-1">{s.text}</span>
                                <span className="text-[10px] text-[var(--text-tertiary)] tabular-nums flex-shrink-0">
                                  {(s.at / 1000).toFixed(1)}s
                                </span>
                              </motion.div>
                            )
                          })}
                        </AnimatePresence>
                      </div>
                    )}
                  </div>
                )}
                {/* Answer */}
                {(m.content || (m.streaming && (!m.steps || m.steps.length === 0))) && (
                  <div className="rounded-lg rounded-bl-sm border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
                    <ProjectMarkdown
                      md={m.content}
                      projectId={projectId}
                      onHoverToken={onHoverToken}
                    />
                    {m.streaming && (
                      <span className="ml-0.5 inline-block w-1.5 h-4 bg-[var(--accent)] animate-pulse align-middle" />
                    )}
                    {/* Footer */}
                    {(!m.streaming && (groundedCount(m) > 0 || m.trace)) && (
                      <div className="mt-3 pt-3 border-t border-[var(--border-subtle)]">
                        {m.trace && (
                          <button
                            onClick={() => setTraceOpen(m.trace as DeepTrace)}
                            className="group flex items-center gap-2 w-full text-left rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/[0.06] px-3 py-2 hover:bg-[var(--accent)]/[0.12] transition-colors"
                          >
                            <Sparkles size={13} className="text-[var(--accent)] flex-shrink-0" />
                            <span className="text-xs font-semibold text-[var(--accent)]">Grounded in {groundedCount(m)} source{groundedCount(m) !== 1 ? 's' : ''}</span>
                            <span className="text-[11px] text-[var(--text-tertiary)] truncate flex-1">
                              {m.trace.sections.length} sections
                              {m.trace.selected_concepts.length ? ` · ${m.trace.selected_concepts.length} concepts` : ''}
                              {(m.trace.facts?.length ?? 0) ? ` · ${m.trace.facts.length} facts` : ''}
                            </span>
                            <ChevronRight size={14} className="ml-auto text-[var(--text-tertiary)] group-hover:text-[var(--accent)] flex-shrink-0" />
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          )}
        </div>
      ) : (
        <div className="flex-1 overflow-y-auto min-h-0">
          <StarterChips projectId={projectId} onSelect={(q) => handleAsk(q)} />
        </div>
      )}

      {error && (
        <p className="text-xs text-red-600 bg-red-50 rounded px-3 py-2 flex-shrink-0">{error}</p>
      )}

      {/* Input */}
      <div className="flex gap-2 items-end flex-shrink-0">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder={messages.length ? 'Ask a follow-up...' : 'Ask anything about this project...'}
          rows={2}
          className="flex-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm text-[var(--text-primary)] resize-none focus:outline-none focus:ring-2 focus:ring-[var(--accent)] disabled:opacity-50"
        />
        <button
          onClick={() => handleAsk()}
          disabled={!question.trim() || isStreaming}
          className="rounded-lg bg-[var(--accent)] px-3 py-2 text-white hover:opacity-90 disabled:opacity-50 self-end"
        >
          <Send size={14} className={isStreaming ? 'animate-pulse' : ''} />
        </button>
      </div>

      <AskTraceDrawer trace={traceOpen} onClose={() => setTraceOpen(null)} />
    </div>
  )
}
