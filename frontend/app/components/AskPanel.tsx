'use client'
import { useState, useRef } from 'react'
import { Send } from 'lucide-react'
import { CitationChip } from './CitationChip'
import { tokenStore } from '@/lib/auth/tokenStore'
import type { CitationItem } from '@/lib/types'

interface Props {
  appId: string
}

export function AskPanel({ appId }: Props) {
  const [question, setQuestion] = useState('')
  const [streamedText, setStreamedText] = useState('')
  const [citations, setCitations] = useState<CitationItem[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  async function handleAsk() {
    if (!question.trim() || isStreaming) return
    setIsStreaming(true)
    setStreamedText('')
    setCitations([])
    setError(null)

    try {
      const res = await fetch(`/api/apps/${appId}/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(tokenStore.get() ? { Authorization: `Bearer ${tokenStore.get()}` } : {}),
        },
        credentials: 'include',
        body: JSON.stringify({ question: question.trim(), top_k: 8 }),
      })

      if (!res.ok || !res.body) {
        setError('Request failed')
        setIsStreaming(false)
        return
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
            if (event.type === 'chunk') setStreamedText((t) => t + event.text)
            if (event.type === 'citations') setCitations(event.citations)
            if (event.type === 'error') setError(event.message)
            if (event.type === 'done') setIsStreaming(false)
          } catch {
            // ignore malformed events
          }
        }
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setIsStreaming(false)
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleAsk()
    }
  }

  return (
    <div className="flex flex-col gap-4">
      {/* Input */}
      <div className="flex gap-2 items-end">
        <textarea
          ref={textareaRef}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder="Ask a question about this application…"
          rows={3}
          className="flex-1 rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3 py-2 text-sm text-[var(--text-primary)] resize-none focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)] disabled:opacity-50"
        />
        <button
          onClick={handleAsk}
          disabled={!question.trim() || isStreaming}
          className="rounded-lg bg-[var(--accent-blue)] px-3 py-2 text-white hover:opacity-90 disabled:opacity-50 self-end"
        >
          <Send size={14} className={isStreaming ? 'animate-pulse' : ''} />
        </button>
      </div>

      {/* Error */}
      {error && (
        <p className="text-xs text-rose-600 bg-rose-50 rounded px-3 py-2">{error}</p>
      )}

      {/* Streaming answer */}
      {streamedText && (
        <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-surface)] p-4">
          <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-wrap">
            {streamedText}
            {isStreaming && <span className="ml-0.5 inline-block w-1.5 h-4 bg-[var(--accent-blue)] animate-pulse" />}
          </p>

          {/* Citation chips */}
          {citations.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-3 pt-3 border-t border-[var(--border-subtle)]">
              {citations.map((c, i) => (
                <CitationChip key={c.id} citation={c} index={i} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
