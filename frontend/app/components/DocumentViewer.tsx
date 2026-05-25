'use client'
import { useEffect, useState } from 'react'
import { FileText, AlertCircle, Clock, X } from 'lucide-react'
import { api } from '@/lib/api'
import { Skeleton } from '@/app/components/Skeleton'
import type { DocumentRead } from '@/lib/types'

interface Props {
  projectId: string
  doc: DocumentRead
  onClose: () => void
}

export function DocumentViewer({ projectId, doc, onClose }: Props) {
  const [text, setText] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    setText(null)
    api.documents.getContent(projectId, doc.id)
      .then((res) => setText(res.text))
      .catch(() => setError('Failed to load document content.'))
      .finally(() => setLoading(false))
  }, [projectId, doc.id])

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4 py-3">
        <FileText size={15} className="shrink-0 text-[var(--accent)]" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{doc.filename}</p>
          <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
            {doc.parse_status === 'pending' && 'Still parsing — content may be incomplete'}
            {doc.parse_status === 'done' && 'Extracted text'}
            {doc.parse_status === 'error' && 'Parse error — content unavailable'}
          </p>
        </div>
        <button
          onClick={onClose}
          className="shrink-0 rounded-lg p-1.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
          aria-label="Close viewer"
        >
          <X size={15} />
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto bg-[var(--bg-base)] p-5">
        {loading && (
          <div className="space-y-2">
            <Skeleton className="h-3 w-3/4" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-5/6" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-2/3" />
          </div>
        )}

        {!loading && error && (
          <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <AlertCircle size={14} className="shrink-0 text-red-500" />
            <p className="text-xs text-red-700">{error}</p>
          </div>
        )}

        {!loading && !error && doc.parse_status === 'pending' && (
          <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
            <Clock size={14} className="shrink-0 text-amber-500" />
            <p className="text-xs text-amber-700">Document is still being parsed. Check back shortly.</p>
          </div>
        )}

        {!loading && !error && text && (
          <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-[var(--text-secondary)]">
            {text}
          </pre>
        )}

        {!loading && !error && !text && doc.parse_status === 'done' && (
          <p className="text-xs text-[var(--text-tertiary)]">No text content extracted from this document.</p>
        )}
      </div>
    </div>
  )
}
