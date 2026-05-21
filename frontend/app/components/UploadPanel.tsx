'use client'
import { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, X } from 'lucide-react'
import clsx from 'clsx'
import { api } from '@/lib/api'

const ALLOWED_TYPES = [
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'text/plain',
]
const MAX_MB = 20

interface UploadFile {
  file: File
  progress: number
  error?: string
}

interface UploadPanelProps {
  projectId: string
  onUploaded: () => void
}

export function UploadPanel({ projectId, onUploaded }: UploadPanelProps) {
  const [queue, setQueue] = useState<UploadFile[]>([])

  const uploadFile = useCallback(async (file: File) => {
    if (!ALLOWED_TYPES.includes(file.type)) {
      setQueue((q) => q.map((i) => i.file === file ? { ...i, error: 'Only PDF, DOCX, TXT files allowed.' } : i))
      return
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setQueue((q) => q.map((i) => i.file === file ? { ...i, error: `Exceeds ${MAX_MB} MB limit.` } : i))
      return
    }
    setQueue((q) => q.map((i) => i.file === file ? { ...i, progress: 10 } : i))
    try {
      await api.documents.upload(projectId, file)
      setQueue((q) => q.filter((i) => i.file !== file))
      onUploaded()
    } catch (err) {
      setQueue((q) => q.map((i) => i.file === file ? { ...i, error: err instanceof Error ? err.message : 'Upload failed.' } : i))
    }
  }, [projectId, onUploaded])

  const onDrop = useCallback((accepted: File[]) => {
    const items: UploadFile[] = accepted.map((f) => ({ file: f, progress: 0 }))
    setQueue((q) => [...q, ...items])
    items.forEach((i) => uploadFile(i.file))
  }, [uploadFile])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'application/pdf': ['.pdf'],
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'],
      'text/plain': ['.txt'],
    },
    maxSize: MAX_MB * 1024 * 1024,
    multiple: true,
  })

  return (
    <div className="px-3 py-4">
      <div
        {...getRootProps()}
        className={clsx(
          'rounded-xl border-2 border-dashed px-4 py-6 text-center cursor-pointer transition-colors',
          isDragActive
            ? 'border-[var(--accent)] bg-accent-subtle'
            : 'border-[var(--border-default)] hover:border-[var(--accent)] hover:bg-[var(--bg-elevated)]'
        )}
      >
        <input {...getInputProps()} />
        <Upload size={20} className="mx-auto mb-2 text-[var(--text-tertiary)]" />
        <p className="text-xs text-[var(--text-secondary)] font-medium">
          {isDragActive ? 'Drop files here' : 'Drop or click to upload'}
        </p>
        <p className="mt-0.5 text-[10px] text-[var(--text-tertiary)]">PDF, DOCX, TXT · max {MAX_MB} MB</p>
      </div>

      {queue.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {queue.map((item, idx) => (
            <li key={idx} className="rounded-lg bg-[var(--bg-elevated)] border border-[var(--border-subtle)] px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-[11px] text-[var(--text-secondary)]">{item.file.name}</span>
                <button
                  onClick={() => setQueue((q) => q.filter((_, i) => i !== idx))}
                  className="shrink-0 text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"
                >
                  <X size={12} />
                </button>
              </div>
              {item.error ? (
                <p className="mt-1 text-[10px] text-danger">{item.error}</p>
              ) : (
                <div className="mt-1.5 h-1 rounded-full bg-[var(--border-default)]">
                  <div
                    className="h-full rounded-full bg-[var(--accent)] transition-all"
                    style={{ width: `${item.progress}%` }}
                  />
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
