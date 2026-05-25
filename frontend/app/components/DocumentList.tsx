'use client'
import { FileText, Trash2, AlertCircle, Clock, CheckCircle2 } from 'lucide-react'
import clsx from 'clsx'
import type { DocumentRead, ParseStatus } from '@/lib/types'
import { api } from '@/lib/api'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

const statusIcon: Record<ParseStatus, React.ReactNode> = {
  pending: <Clock size={12} className="text-warning" />,
  done:    <CheckCircle2 size={12} className="text-emerald-500" />,
  error:   <AlertCircle size={12} className="text-danger" />,
}

const statusLabel: Record<ParseStatus, string> = {
  pending: 'Parsing…',
  done:    'Ready',
  error:   'Parse error',
}

interface DocumentListProps {
  projectId: string
  documents: DocumentRead[]
  selectedId?: string | null
  onSelect?: (doc: DocumentRead) => void
  onDeleted: () => void
}

export function DocumentList({ projectId, documents, selectedId, onSelect, onDeleted }: DocumentListProps) {
  async function handleDelete(e: React.MouseEvent, docId: string) {
    e.stopPropagation()
    try {
      await api.documents.delete(projectId, docId)
      onDeleted()
    } catch {
      // silently fail — user can retry
    }
  }

  if (documents.length === 0) {
    return (
      <p className="px-1 py-2 text-[11px] text-[var(--text-tertiary)]">No documents uploaded yet.</p>
    )
  }

  return (
    <ul className="space-y-1">
      {documents.map((doc) => (
        <li key={doc.id}>
          <button
            onClick={() => onSelect?.(doc)}
            className={clsx(
              'group flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors',
              selectedId === doc.id
                ? 'bg-[var(--accent-subtle)]/40 border border-[var(--accent)]/30'
                : 'hover:bg-[var(--bg-elevated)] border border-transparent'
            )}
          >
            <FileText
              size={14}
              className={clsx(
                'shrink-0',
                selectedId === doc.id ? 'text-[var(--accent)]' : 'text-[var(--text-tertiary)]'
              )}
            />
            <div className="min-w-0 flex-1">
              <p className={clsx(
                'truncate text-xs font-medium leading-none',
                selectedId === doc.id ? 'text-[var(--accent-deep)]' : 'text-[var(--text-primary)]'
              )}>
                {doc.filename}
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--text-tertiary)]">
                {formatBytes(doc.size_bytes)} · {statusLabel[doc.parse_status]}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {statusIcon[doc.parse_status]}
              <button
                onClick={(e) => handleDelete(e, doc.id)}
                className={clsx(
                  'rounded p-1 text-[var(--text-tertiary)] hover:text-danger hover:bg-danger-bg transition-colors',
                  'opacity-0 group-hover:opacity-100'
                )}
                aria-label={`Delete ${doc.filename}`}
              >
                <Trash2 size={11} />
              </button>
            </div>
          </button>
        </li>
      ))}
    </ul>
  )
}
