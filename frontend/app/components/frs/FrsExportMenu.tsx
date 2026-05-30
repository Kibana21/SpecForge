'use client'
/**
 * Header dropdown: Export menu. Today supports the Markdown bundle (.zip).
 * Future formats (DOCX, public link) are rendered disabled.
 */
import { useEffect, useRef, useState } from 'react'
import { ChevronDown, Download, FileText, Link2, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'

interface Props {
  projectId: string
  /** Suggested filename prefix (e.g. project name). */
  filenamePrefix?: string
}

export function FrsExportMenu({ projectId, filenamePrefix }: Props) {
  const [open, setOpen] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const wrapRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onDown(e: MouseEvent) {
      if (!wrapRef.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  async function handleMarkdown() {
    setDownloading(true)
    try {
      const blob = await api.frs.exportBundle(projectId)
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
      const prefix = (filenamePrefix ?? 'frs').replace(/\s+/g, '_')
      a.download = `${prefix}-${ts}.zip`
      document.body.appendChild(a)
      a.click()
      a.remove()
      URL.revokeObjectURL(url)
      toast.success('Bundle downloaded')
      setOpen(false)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Export failed')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div ref={wrapRef} className="relative">
      <button
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-2.5 py-1.5 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
      >
        <Download size={13} />
        Export
        <ChevronDown size={11} />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-1 w-56 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-[var(--shadow-md)] overflow-hidden z-30"
        >
          <button
            onClick={handleMarkdown}
            disabled={downloading}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 text-xs text-left hover:bg-[var(--accent-subtle)] hover:text-[var(--accent)] disabled:opacity-50 transition-colors',
            )}
          >
            {downloading
              ? <Loader2 size={12} className="animate-spin" />
              : <FileText size={12} />}
            <span className="font-semibold">Markdown bundle (.zip)</span>
          </button>
          <div className="border-t border-[var(--border-subtle)]" />
          <button
            disabled
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left text-[var(--text-tertiary)] cursor-not-allowed"
            title="Coming soon"
          >
            <FileText size={12} />
            <span>DOCX</span>
            <span className="ml-auto text-[10px]">soon</span>
          </button>
          <button
            disabled
            className="w-full flex items-center gap-2 px-3 py-2 text-xs text-left text-[var(--text-tertiary)] cursor-not-allowed"
            title="Coming soon"
          >
            <Link2 size={12} />
            <span>Copy public link</span>
            <span className="ml-auto text-[10px]">soon</span>
          </button>
        </div>
      )}
    </div>
  )
}
