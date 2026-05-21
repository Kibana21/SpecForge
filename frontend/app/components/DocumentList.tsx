'use client'
import { FileText, Trash2, AlertCircle, Clock } from 'lucide-react'
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
  done: null,
  error: <AlertCircle size={12} className="text-danger" />,
}

interface DocumentListProps {
  projectId: string
  documents: DocumentRead[]
  onDeleted: () => void
}

export function DocumentList({ projectId, documents, onDeleted }: DocumentListProps) {
  async function handleDelete(docId: string) {
    try {
      await api.documents.delete(projectId, docId)
      onDeleted()
    } catch {
      // silently fail — user can retry
    }
  }

  return (
    <ul className="space-y-1 px-3 pb-3">
      {documents.map((doc) => (
        <li
          key={doc.id}
          className="group flex items-center gap-2.5 rounded-lg px-3 py-2.5 hover:bg-[var(--bg-elevated)] transition-colors"
        >
          <FileText size={14} className="shrink-0 text-[var(--text-tertiary)]" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs text-[var(--text-primary)]">{doc.filename}</p>
            <p className="text-[10px] text-[var(--text-tertiary)]">{formatBytes(doc.size_bytes)}</p>
          </div>
          <div className="flex items-center gap-1.5">
            {statusIcon[doc.parse_status]}
            <button
              onClick={() => handleDelete(doc.id)}
              className={clsx(
                'rounded p-1 text-[var(--text-tertiary)] hover:text-danger hover:bg-danger-bg transition-colors',
                'opacity-0 group-hover:opacity-100'
              )}
              aria-label={`Delete ${doc.filename}`}
            >
              <Trash2 size={12} />
            </button>
          </div>
        </li>
      ))}
    </ul>
  )
}
