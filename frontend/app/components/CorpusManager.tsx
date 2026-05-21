'use client'
import { useRef, useState } from 'react'
import { Upload, RefreshCw } from 'lucide-react'
import { IndexStatusBadge } from './IndexStatusBadge'
import { api } from '@/lib/api'
import type { AppCorpusDoc } from '@/lib/types'

interface Props {
  appId: string
  docs: AppCorpusDoc[]
  canWrite: boolean
  rebuildStatus: string | null
  onRefresh: () => void
}

export function CorpusManager({ appId, docs, canWrite, rebuildStatus, onRefresh }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uploading, setUploading] = useState(false)
  const [reindexing, setReindexing] = useState(rebuildStatus === 'rebuilding')
  const [error, setError] = useState<string | null>(null)

  async function handleUpload(files: FileList | null) {
    if (!files || files.length === 0) return
    setUploading(true)
    setError(null)
    try {
      await api.apps.uploadCorpusDoc(appId, files[0])
      onRefresh()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  async function handleReindex() {
    setReindexing(true)
    setError(null)
    try {
      await api.apps.reindex(appId)
      onRefresh()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Reindex failed')
    } finally {
      setTimeout(() => setReindexing(false), 2000)
    }
  }

  return (
    <div className="space-y-4">
      {error && (
        <p className="text-xs text-rose-600 bg-rose-50 rounded px-3 py-2">{error}</p>
      )}

      {/* Doc list */}
      {docs.length > 0 ? (
        <div className="divide-y divide-[var(--border-subtle)] rounded-lg border border-[var(--border-default)]">
          {docs.map((doc) => (
            <div key={doc.id} className="flex items-center justify-between px-3 py-2.5 gap-3">
              <div className="min-w-0 flex-1">
                <p className="text-xs text-[var(--text-primary)] truncate">{doc.name}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  {doc.page_count && (
                    <span className="text-[10px] text-[var(--text-tertiary)]">{doc.page_count}p</span>
                  )}
                  {doc.is_primary && (
                    <span className="text-[10px] font-medium text-[var(--accent-blue)]">Primary</span>
                  )}
                </div>
              </div>
              <IndexStatusBadge status={doc.index_status} />
            </div>
          ))}
        </div>
      ) : (
        <p className="text-xs text-[var(--text-tertiary)]">No corpus documents yet.</p>
      )}

      {/* Actions */}
      {canWrite && (
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="file"
            accept=".pdf,.docx,.txt"
            className="hidden"
            onChange={(e) => handleUpload(e.target.files)}
          />
          <button
            onClick={() => inputRef.current?.click()}
            disabled={uploading}
            className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
          >
            <Upload size={12} className={uploading ? 'animate-pulse' : ''} />
            {uploading ? 'Uploading…' : 'Upload Document'}
          </button>
          {docs.length > 0 && (
            <button
              onClick={handleReindex}
              disabled={reindexing || rebuildStatus === 'rebuilding'}
              className="flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] px-3 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] disabled:opacity-50"
            >
              <RefreshCw size={12} className={reindexing ? 'animate-spin' : ''} />
              {reindexing || rebuildStatus === 'rebuilding' ? 'Rebuilding…' : 'Re-index All'}
            </button>
          )}
        </div>
      )}
    </div>
  )
}
