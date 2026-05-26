'use client'
import { AlignLeft, AlertCircle, File, FileText, Hash, Image, Loader2, CheckCircle2, RotateCcw, Trash2 } from 'lucide-react'
import clsx from 'clsx'
import type { DocumentRead } from '@/lib/types'
import { api } from '@/lib/api'

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function mimeIcon(mime: string): { icon: React.ReactNode; tint: string } {
  if (mime.includes('pdf')) return { icon: <FileText size={14} />, tint: 'text-red-400' }
  if (mime.includes('word') || mime.includes('docx')) return { icon: <FileText size={14} />, tint: 'text-blue-400' }
  if (mime.includes('markdown')) return { icon: <Hash size={14} />, tint: 'text-purple-400' }
  if (mime.includes('plain') || mime.includes('txt')) return { icon: <AlignLeft size={14} />, tint: 'text-[var(--text-tertiary)]' }
  if (mime.startsWith('image/')) return { icon: <Image size={14} />, tint: 'text-amber-400' }
  return { icon: <File size={14} />, tint: 'text-[var(--text-tertiary)]' }
}

function IndexingIndicator({ status, error }: { status: string; error: string | null }) {
  if (status === 'done') return <CheckCircle2 size={12} className="shrink-0 text-emerald-500" />
  if (status === 'running') return <Loader2 size={12} className="shrink-0 text-[var(--accent)] animate-spin" />
  if (status === 'error') return (
    <span title={error ?? 'Index error'}>
      <AlertCircle size={12} className="shrink-0 text-danger" />
    </span>
  )
  return <Loader2 size={12} className="shrink-0 text-[var(--text-tertiary)] animate-pulse" />
}

function indexingLabel(status: string): string {
  if (status === 'done') return 'Indexed'
  if (status === 'running') return 'Indexing…'
  if (status === 'error') return 'Index error'
  return 'In queue'
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
      // silently fail
    }
  }

  async function handleReindex(e: React.MouseEvent, docId: string) {
    e.stopPropagation()
    try {
      await api.documents.reindex(projectId, docId)
      // SWR polling (every 3s when any doc is non-done) picks up the new pending status
    } catch {
      // silently fail
    }
  }

  if (documents.length === 0) {
    return (
      <p className="px-1 py-2 text-[11px] text-[var(--text-tertiary)]">No documents uploaded yet.</p>
    )
  }

  return (
    <ul className="space-y-1">
      {documents.map((doc) => {
        const { icon, tint } = mimeIcon(doc.mime_type)
        const isSelected = selectedId === doc.id
        return (
          <li key={doc.id}>
            <button
              onClick={() => onSelect?.(doc)}
              className={clsx(
                'group flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left transition-colors',
                isSelected
                  ? 'bg-[var(--accent-subtle)]/40 border border-[var(--accent)]/30'
                  : 'hover:bg-[var(--bg-elevated)] border border-transparent'
              )}
            >
              <span className={clsx('shrink-0', isSelected ? 'text-[var(--accent)]' : tint)}>
                {icon}
              </span>
              <div className="min-w-0 flex-1">
                <p className={clsx(
                  'truncate text-xs font-medium leading-none',
                  isSelected ? 'text-[var(--accent-deep)]' : 'text-[var(--text-primary)]'
                )}>
                  {doc.filename}
                </p>
                <p className="mt-0.5 text-[10px] text-[var(--text-tertiary)]">
                  {formatBytes(doc.size_bytes)} · {indexingLabel(doc.indexing_status)}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-1.5">
                <IndexingIndicator status={doc.indexing_status} error={doc.index_error} />
                {doc.indexing_status === 'error' && (
                  <button
                    onClick={(e) => handleReindex(e, doc.id)}
                    title="Retry indexing"
                    className="rounded p-1 text-[var(--text-tertiary)] hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)] transition-colors"
                  >
                    <RotateCcw size={11} />
                  </button>
                )}
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
        )
      })}
    </ul>
  )
}
