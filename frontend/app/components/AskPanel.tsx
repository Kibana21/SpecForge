'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { Send, Zap, Telescope, Check, Loader2, Plus, MessageSquare, History, Trash2, Sparkles, ChevronRight } from 'lucide-react'
import { motion, AnimatePresence } from 'framer-motion'
import { CitationChip } from './CitationChip'
import { AskTraceDrawer } from './AskTraceDrawer'
import { Markdown } from './Markdown'
import { api, authedFetch } from '@/lib/api'
import type { CitationItem, AskMode, AskSessionListItem, AskSessionMessage, DeepTrace } from '@/lib/types'

interface Props {
  appId: string
}

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  mode?: AskMode
  citations?: CitationItem[]
  steps?: string[]
  trace?: DeepTrace
  streaming?: boolean
}

const MODES: { key: AskMode; label: string; icon: typeof Zap; hint: string }[] = [
  { key: 'quick', label: 'Quick', icon: Zap, hint: 'Fast single-pass search over the corpus' },
  { key: 'deep', label: 'Deep', icon: Telescope, hint: 'Reasons over the Brain Wiki, drilling into source sections' },
]

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

export function AskPanel({ appId }: Props) {
  const [question, setQuestion] = useState('')
  const [mode, setMode] = useState<AskMode>('quick')
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<AskSessionListItem[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [traceOpen, setTraceOpen] = useState<DeepTrace | null>(null)
  const threadRef = useRef<HTMLDivElement>(null)
  const sessionIdRef = useRef<string | null>(null)

  const loadSessions = useCallback(async () => {
    try { setSessions(await api.apps.listAskSessions(appId)) } catch { /* ignore */ }
  }, [appId])

  useEffect(() => { loadSessions() }, [loadSessions])

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  function applyMessages(updater: (prev: ChatMessage[]) => ChatMessage[]) {
    setMessages(updater)
  }

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
    // Compact, space-efficient transcript: role/content/mode + minimal citation refs.
    if (msgs.length < 2) return
    const compact: AskSessionMessage[] = msgs.map((m) => ({
      role: m.role,
      content: m.content,
      ...(m.role === 'assistant'
        ? {
            mode: m.mode,
            citations: (m.citations ?? []).map((c) => ({ id: c.id, doc_name: c.doc_name, chunk_no: c.chunk_no })),
            trace: m.trace,
          }
        : {}),
    }))
    const title = (msgs.find((m) => m.role === 'user')?.content ?? 'Chat').slice(0, 80)
    try {
      const res = await api.apps.saveAskSession(appId, { id: sessionIdRef.current, title, messages: compact })
      sessionIdRef.current = res.id
      loadSessions()
    } catch { /* non-fatal */ }
  }

  async function handleAsk() {
    const q = question.trim()
    if (!q || isStreaming) return

    const history = messages.slice(-MAX_HISTORY_TURNS).map((m) => ({ role: m.role, content: m.content }))

    applyMessages((prev) => [
      ...prev,
      { role: 'user', content: q },
      { role: 'assistant', content: '', mode, citations: [], steps: [], streaming: true },
    ])
    setQuestion('')
    setError(null)
    setIsStreaming(true)

    try {
      const res = await authedFetch(`/api/apps/${appId}/ask`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: q, top_k: 8, mode, history }),
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
            if (event.type === 'step') updateLastAssistant((m) => ({ ...m, steps: [...(m.steps ?? []), event.text] }))
            if (event.type === 'chunk') updateLastAssistant((m) => ({ ...m, content: m.content + event.text }))
            if (event.type === 'trace') updateLastAssistant((m) => ({ ...m, trace: event.trace }))
            if (event.type === 'citations') updateLastAssistant((m) => ({ ...m, citations: event.citations }))
            if (event.type === 'error') { setError(event.message); updateLastAssistant((m) => ({ ...m, content: m.content || event.message, streaming: false })) }
            if (event.type === 'done') updateLastAssistant((m) => ({ ...m, streaming: false }))
          } catch { /* ignore malformed */ }
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      updateLastAssistant((m) => ({ ...m, streaming: false }))
      setIsStreaming(false)
      setMessages((prev) => { void persist(prev); return prev })  // autosave with final transcript
    }
  }

  function newChat() {
    setMessages([]); setError(null); sessionIdRef.current = null; setShowHistory(false)
  }

  async function replaySession(sid: string) {
    try {
      const data = await api.apps.getAskSession(appId, sid)
      const msgs: ChatMessage[] = data.messages.map((m) => ({
        role: m.role,
        content: m.content,
        mode: m.mode,
        citations: (m.citations ?? []).map((c) => ({ ...c, text_excerpt: '' })),
        trace: m.trace,
        streaming: false,
      }))
      setMessages(msgs)
      sessionIdRef.current = data.id
      setShowHistory(false)
      setError(null)
    } catch {
      setError('Could not load that session')
    }
  }

  async function removeSession(sid: string, e: React.MouseEvent) {
    e.stopPropagation()
    try {
      await api.apps.deleteAskSession(appId, sid)
      if (sessionIdRef.current === sid) newChat()
      loadSessions()
    } catch { /* ignore */ }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleAsk() }
  }

  const activeHint = MODES.find((m) => m.key === mode)?.hint

  return (
    <div className="flex flex-col gap-3">
      {/* Top bar: mode toggle + history + new chat */}
      <div className="flex items-center gap-3">
        <div className="inline-flex rounded-lg border border-[var(--border-default)] bg-[var(--bg-elevated)] p-0.5">
          {MODES.map((m) => {
            const Icon = m.icon
            const active = mode === m.key
            return (
              <button key={m.key} onClick={() => setMode(m.key)} disabled={isStreaming}
                className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-all disabled:opacity-50 ${
                  active ? 'bg-[var(--bg-surface)] text-[var(--accent)] shadow-sm' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
                }`}>
                <Icon size={13} />{m.label}
              </button>
            )
          })}
        </div>
        <p className="text-[11px] text-[var(--text-tertiary)] flex-1 truncate">{activeHint}</p>

        {/* History */}
        <div className="relative">
          <button onClick={() => setShowHistory((s) => !s)}
            className={`flex items-center gap-1.5 text-[11px] px-2 py-1 rounded-md transition-colors ${
              showHistory ? 'bg-[var(--bg-elevated)] text-[var(--text-secondary)]' : 'text-[var(--text-tertiary)] hover:text-[var(--text-secondary)]'
            }`}>
            <History size={12} /> History{sessions.length ? ` (${sessions.length})` : ''}
          </button>
          {showHistory && (
            <div className="absolute right-0 z-20 mt-1 w-72 max-h-80 overflow-y-auto rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-lg p-1">
              {sessions.length === 0 ? (
                <p className="text-[11px] text-[var(--text-tertiary)] px-3 py-3 text-center">No saved chats yet.</p>
              ) : sessions.map((s) => (
                <div key={s.id} onClick={() => replaySession(s.id)}
                  className="group flex items-center gap-2 px-2.5 py-2 rounded-md hover:bg-[var(--bg-elevated)] cursor-pointer">
                  <MessageSquare size={12} className="text-[var(--text-tertiary)] flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs text-[var(--text-primary)] truncate">{s.title}</p>
                    <p className="text-[10px] text-[var(--text-tertiary)]">{s.message_count} msgs · {relativeTime(s.updated_at)}</p>
                  </div>
                  <button onClick={(e) => removeSession(s.id, e)}
                    className="opacity-0 group-hover:opacity-100 text-[var(--text-tertiary)] hover:text-red-500 flex-shrink-0">
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {messages.length > 0 && (
          <button onClick={newChat} disabled={isStreaming}
            className="flex items-center gap-1.5 text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] disabled:opacity-50">
            <Plus size={12} /> New chat
          </button>
        )}
      </div>

      {/* Thread */}
      {messages.length > 0 && (
        <div ref={threadRef} className="flex flex-col gap-3 max-h-[calc(100vh-340px)] overflow-y-auto pr-1">
          {messages.map((m, i) =>
            m.role === 'user' ? (
              <div key={i} className="self-end max-w-[85%] rounded-lg rounded-br-sm bg-[var(--accent)] text-white px-3 py-2 text-sm whitespace-pre-wrap">
                {m.content}
              </div>
            ) : (
              <div key={i} className="self-start w-full">
                {m.steps && m.steps.length > 0 && (
                  <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] px-3 py-2 mb-1.5 space-y-1.5">
                    <AnimatePresence initial={false}>
                      {m.steps.map((s, si) => {
                        const pending = m.streaming && si === m.steps!.length - 1 && !m.content
                        return (
                          <motion.div key={si} initial={{ opacity: 0, x: -4 }} animate={{ opacity: 1, x: 0 }}
                            className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)]">
                            {pending ? <Loader2 size={11} className="animate-spin text-[var(--accent)] flex-shrink-0" />
                              : <Check size={11} className="text-emerald-500 flex-shrink-0" />}
                            {s}
                          </motion.div>
                        )
                      })}
                    </AnimatePresence>
                  </div>
                )}
                {(m.content || (m.streaming && (!m.steps || m.steps.length === 0))) && (
                  <div className="rounded-lg rounded-bl-sm border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-3">
                    <div className="text-sm text-[var(--text-primary)]">
                      <Markdown md={m.content} />
                      {m.streaming && <span className="ml-0.5 inline-block w-1.5 h-4 bg-[var(--accent)] animate-pulse align-middle" />}
                    </div>
                    {((m.citations && m.citations.length > 0) || m.trace) && (
                      <div className="mt-3 pt-3 border-t border-[var(--border-subtle)] space-y-2">
                        {m.trace && (
                          <button onClick={() => setTraceOpen(m.trace!)}
                            className="group flex items-center gap-2 w-full text-left rounded-lg border border-[var(--accent)]/30 bg-[var(--accent)]/[0.06] px-3 py-2 hover:bg-[var(--accent)]/[0.12] transition-colors">
                            <Sparkles size={13} className="text-[var(--accent)] flex-shrink-0" />
                            <span className="text-xs font-semibold text-[var(--accent)]">View answer trace</span>
                            <span className="text-[11px] text-[var(--text-tertiary)] truncate">
                              {m.trace.selected_concepts.length} concepts · {m.trace.sections.length} sections{m.trace.chunks.length ? ` · ${m.trace.chunks.length} chunks` : ''}
                            </span>
                            <ChevronRight size={14} className="ml-auto text-[var(--text-tertiary)] group-hover:text-[var(--accent)] flex-shrink-0" />
                          </button>
                        )}
                        {m.citations && m.citations.length > 0 && (
                          <div className="flex flex-wrap gap-1.5">
                            {m.citations.map((c, ci) => (
                              <motion.div key={c.id} initial={{ opacity: 0, scale: 0.85 }} animate={{ opacity: 1, scale: 1 }}
                                transition={{ delay: ci * 0.04, type: 'spring', stiffness: 500, damping: 30 }}>
                                <CitationChip citation={c} index={ci} />
                              </motion.div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          )}
        </div>
      )}

      {/* Empty state */}
      {messages.length === 0 && (
        <div className="flex flex-col items-center gap-2 py-6 text-center">
          <div className="w-11 h-11 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
            <MessageSquare size={18} className="text-[var(--text-tertiary)]" strokeWidth={1.5} />
          </div>
          <p className="text-xs text-[var(--text-tertiary)] max-w-[320px]">
            Ask a question about this application. Use <strong>Deep</strong> for cross-document reasoning with cited sources. Chats are saved automatically — find them under <strong>History</strong>.
          </p>
        </div>
      )}

      {error && <p className="text-xs text-danger bg-danger-bg rounded px-3 py-2">{error}</p>}

      {/* Input */}
      <div className="flex gap-2 items-end">
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder={messages.length ? 'Ask a follow-up…' : 'Ask a question about this application…'}
          rows={2}
          className="flex-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm text-[var(--text-primary)] resize-none focus:outline-none focus:ring-2 focus:ring-[var(--accent)] disabled:opacity-50"
        />
        <button onClick={handleAsk} disabled={!question.trim() || isStreaming}
          className="rounded-lg bg-[var(--accent)] px-3 py-2 text-white hover:opacity-90 disabled:opacity-50 self-end">
          <Send size={14} className={isStreaming ? 'animate-pulse' : ''} />
        </button>
      </div>

      <AskTraceDrawer trace={traceOpen} onClose={() => setTraceOpen(null)} />
    </div>
  )
}
