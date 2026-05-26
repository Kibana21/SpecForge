'use client'
import { useEffect, useState } from 'react'
import { AlertCircle, ChevronRight, FileText, Hash, AlignLeft, Image as ImageIcon, Loader2, X, File } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '@/lib/api'
import { Skeleton } from '@/app/components/Skeleton'
import type { DocumentOutlineNode, DocumentRead, DocumentSection } from '@/lib/types'

interface Props {
  projectId: string
  doc: DocumentRead
  onClose: () => void
}

type Tab = 'ai' | 'rendered' | 'text' | 'structure'

function getTabs(mime: string): Tab[] {
  if (mime.startsWith('image/')) return ['ai', 'structure']
  if (mime === 'text/markdown') return ['rendered', 'structure']
  if (mime === 'text/plain') return ['text']
  return ['rendered', 'structure']
}

function tabLabel(tab: Tab): string {
  if (tab === 'ai') return 'AI Understanding'
  if (tab === 'rendered') return 'Rendered'
  if (tab === 'text') return 'Text'
  return 'Structure'
}

function MimeIcon({ mime, className }: { mime: string; className?: string }) {
  const cls = className ?? 'size-4 shrink-0'
  if (mime.includes('pdf')) return <FileText className={cls} />
  if (mime.includes('word') || mime.includes('docx')) return <FileText className={cls} />
  if (mime.includes('markdown')) return <Hash className={cls} />
  if (mime.includes('plain')) return <AlignLeft className={cls} />
  if (mime.startsWith('image/')) return <ImageIcon className={cls} />
  return <File className={cls} />
}

// ── Rendered markdown ────────────────────────────────────────────────────────

function MarkdownBody({ text }: { text: string }) {
  return (
    <div className="text-sm text-[var(--text-secondary)] leading-relaxed [&_h1]:text-xl [&_h1]:font-bold [&_h1]:text-[var(--text-primary)] [&_h1]:mt-4 [&_h1]:mb-2 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-[var(--text-primary)] [&_h2]:mt-4 [&_h2]:mb-2 [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-[var(--text-primary)] [&_h3]:mt-3 [&_h3]:mb-1 [&_p]:mb-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-2 [&_li]:mb-0.5 [&_strong]:text-[var(--text-primary)] [&_strong]:font-semibold [&_code]:text-[var(--accent-deep)] [&_code]:bg-[var(--accent-subtle)]/30 [&_code]:px-1 [&_code]:rounded [&_code]:text-xs [&_pre]:bg-[var(--bg-elevated)] [&_pre]:border [&_pre]:border-[var(--border-default)] [&_pre]:rounded-lg [&_pre]:p-3 [&_pre]:overflow-x-auto [&_pre]:text-xs [&_pre]:mb-3 [&_table]:w-full [&_table]:border-collapse [&_table]:text-xs [&_table]:mb-3 [&_th]:border [&_th]:border-[var(--border-default)] [&_th]:px-2 [&_th]:py-1 [&_th]:bg-[var(--bg-elevated)] [&_th]:text-left [&_td]:border [&_td]:border-[var(--border-default)] [&_td]:px-2 [&_td]:py-1 [&_blockquote]:border-l-2 [&_blockquote]:border-[var(--accent)] [&_blockquote]:pl-3 [&_blockquote]:text-[var(--text-tertiary)] [&_blockquote]:italic [&_hr]:border-[var(--border-default)] [&_hr]:my-4 [&_a]:text-[var(--accent)] [&_a]:no-underline hover:[&_a]:underline">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{text}</ReactMarkdown>
    </div>
  )
}

// ── Structure tree ───────────────────────────────────────────────────────────

function StructureNode({
  projectId, docId, node,
}: {
  projectId: string
  docId: string
  node: DocumentOutlineNode
}) {
  const [open, setOpen] = useState(false)
  const [section, setSection] = useState<DocumentSection | null>(null)
  const [loadingSection, setLoadingSection] = useState(false)
  const hasChildren = node.children.length > 0

  async function expand() {
    const next = !open
    setOpen(next)
    if (next && !section && !loadingSection) {
      setLoadingSection(true)
      try {
        const s = await api.documents.getSection(projectId, docId, node.node_id)
        setSection(s)
      } catch {
        // leave section null — show error state
      } finally {
        setLoadingSection(false)
      }
    }
  }

  return (
    <div className={node.depth > 0 ? 'ml-4 border-l border-[var(--border-subtle)] pl-3' : ''}>
      <div className="group flex items-start gap-2 rounded-lg px-2 py-1.5 hover:bg-[var(--bg-elevated)] transition-colors">
        <button
          onClick={expand}
          className="mt-0.5 shrink-0 rounded p-0.5 text-[var(--text-tertiary)] hover:text-[var(--text-primary)] transition-colors"
          aria-label={open ? 'Collapse' : 'Expand'}
        >
          <ChevronRight
            size={12}
            className={`transition-transform duration-150 ${open ? 'rotate-90' : ''}`}
          />
        </button>
        <div className="min-w-0 flex-1 cursor-pointer" onClick={expand}>
          <p className="text-xs font-medium text-[var(--text-primary)] leading-snug">{node.title || '(untitled)'}</p>
          <div className="flex items-center gap-2 mt-0.5">
            {node.pages && (
              <span className="shrink-0 whitespace-nowrap text-[10px] text-[var(--text-tertiary)]">{node.pages}</span>
            )}
            {node.summary && (
              <span className="text-[10px] text-[var(--text-tertiary)] truncate">{node.summary}</span>
            )}
          </div>
        </div>
      </div>

      {open && (
        <div className="ml-6">
          {loadingSection && (
            <div className="space-y-1.5 py-1.5">
              <Skeleton className="h-2.5 w-3/4" />
              <Skeleton className="h-2.5 w-full" />
              <Skeleton className="h-2.5 w-5/6" />
            </div>
          )}
          {!loadingSection && section && section.text && (
            <pre className="whitespace-pre-wrap break-words font-mono text-[11px] leading-relaxed text-[var(--text-secondary)] py-1.5 pr-2">
              {section.text}
            </pre>
          )}
          {!loadingSection && section && !section.text && (
            <p className="text-[10px] text-[var(--text-tertiary)] py-1">No text content for this section.</p>
          )}
          {!loadingSection && !section && open && (
            <p className="text-[10px] text-danger py-1">Failed to load section text.</p>
          )}
          {hasChildren && (
            <div className="mt-0.5 space-y-0.5">
              {node.children.map((child) => (
                <StructureNode key={child.node_id} projectId={projectId} docId={docId} node={child} />
              ))}
            </div>
          )}
        </div>
      )}

      {!open && hasChildren && (
        <div className="ml-6 space-y-0.5">
          {node.children.map((child) => (
            <StructureNode key={child.node_id} projectId={projectId} docId={docId} node={child} />
          ))}
        </div>
      )}
    </div>
  )
}

// ── Main viewer ──────────────────────────────────────────────────────────────

export function DocumentViewer({ projectId, doc, onClose }: Props) {
  const tabs = getTabs(doc.mime_type)
  const [activeTab, setActiveTab] = useState<Tab>(tabs[0])

  // Text content (for 'ai', 'rendered', 'text' tabs)
  const [text, setText] = useState<string | null>(null)
  const [textLoading, setTextLoading] = useState(true)
  const [textError, setTextError] = useState<string | null>(null)

  // Outline (for 'structure' tab)
  const [outline, setOutline] = useState<DocumentOutlineNode[] | null>(null)
  const [outlineLoading, setOutlineLoading] = useState(false)
  const [outlineError, setOutlineError] = useState<string | null>(null)

  // File URL (for image thumbnail)
  const fileUrl = api.documents.getFileUrl(projectId, doc.id)

  // Load text content on mount
  useEffect(() => {
    setTextLoading(true)
    setTextError(null)
    setText(null)
    api.documents.getContent(projectId, doc.id)
      .then((res) => setText(res.text))
      .catch(() => setTextError('Failed to load document content.'))
      .finally(() => setTextLoading(false))
  }, [projectId, doc.id])

  // Load outline when structure tab becomes active
  useEffect(() => {
    if (activeTab !== 'structure' || outline !== null || outlineLoading) return
    setOutlineLoading(true)
    setOutlineError(null)
    api.documents.getOutline(projectId, doc.id)
      .then((res) => setOutline(res.nodes))
      .catch(() => setOutlineError('Failed to load document structure.'))
      .finally(() => setOutlineLoading(false))
  }, [activeTab, projectId, doc.id, outline, outlineLoading])

  // Reset state when doc changes
  useEffect(() => {
    setActiveTab(getTabs(doc.mime_type)[0])
    setText(null)
    setTextLoading(true)
    setTextError(null)
    setOutline(null)
    setOutlineLoading(false)
    setOutlineError(null)
  }, [doc.id, doc.mime_type])

  const isIndexing = doc.indexing_status === 'running' || doc.indexing_status === 'pending'

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="shrink-0 border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
        {/* Image thumbnail strip */}
        {doc.mime_type.startsWith('image/') && (
          <div className="flex items-center gap-3 px-4 pt-3 pb-0">
            <div className="h-16 w-24 shrink-0 overflow-hidden rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] flex items-center justify-center">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={fileUrl}
                alt={doc.filename}
                className="h-full w-full object-contain"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{doc.filename}</p>
              <span className="mt-0.5 inline-flex items-center gap-1 text-[10px] text-[var(--accent-deep)] bg-[var(--accent-subtle)]/30 px-1.5 py-0.5 rounded font-medium">
                AI Understanding
              </span>
            </div>
            <button
              onClick={onClose}
              className="shrink-0 rounded-lg p-1.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
              aria-label="Close viewer"
            >
              <X size={15} />
            </button>
          </div>
        )}

        {/* Standard header for non-images */}
        {!doc.mime_type.startsWith('image/') && (
          <div className="flex items-center gap-3 px-4 py-3">
            <MimeIcon mime={doc.mime_type} className="size-4 shrink-0 text-[var(--accent)]" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{doc.filename}</p>
              <p className="text-[10px] text-[var(--text-tertiary)] mt-0.5">
                {isIndexing ? 'Indexing document…' : doc.indexing_status === 'done' ? 'Indexed' : 'Index error'}
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
        )}

        {/* Tab bar */}
        {tabs.length > 1 && (
          <div className="flex gap-0 px-3 pb-0">
            {tabs.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={[
                  'px-3 py-2 text-xs font-medium border-b-2 transition-colors',
                  activeTab === tab
                    ? 'border-[var(--accent)] text-[var(--accent-deep)]'
                    : 'border-transparent text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
                ].join(' ')}
              >
                {tabLabel(tab)}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto bg-[var(--bg-base)]">
        {/* AI Understanding / Rendered tabs */}
        {(activeTab === 'ai' || activeTab === 'rendered') && (
          <div className="p-5">
            {textLoading && (
              <div className="space-y-2">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-2/3" />
              </div>
            )}
            {!textLoading && textError && (
              <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                <AlertCircle size={14} className="shrink-0 text-red-500" />
                <p className="text-xs text-red-700">{textError}</p>
              </div>
            )}
            {!textLoading && !textError && isIndexing && (
              <div className="flex items-center gap-2 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3">
                <Loader2 size={14} className="shrink-0 text-blue-500 animate-spin" />
                <p className="text-xs text-blue-700">Document is being processed. Check back shortly.</p>
              </div>
            )}
            {!textLoading && !textError && text && <MarkdownBody text={text} />}
            {!textLoading && !textError && !text && !isIndexing && (
              <p className="text-xs text-[var(--text-tertiary)]">No content extracted from this document.</p>
            )}
          </div>
        )}

        {/* Text tab (plain) */}
        {activeTab === 'text' && (
          <div className="p-5">
            {textLoading && (
              <div className="space-y-2">
                <Skeleton className="h-3 w-3/4" />
                <Skeleton className="h-3 w-full" />
                <Skeleton className="h-3 w-5/6" />
              </div>
            )}
            {!textLoading && textError && (
              <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                <AlertCircle size={14} className="shrink-0 text-red-500" />
                <p className="text-xs text-red-700">{textError}</p>
              </div>
            )}
            {!textLoading && !textError && text && (
              <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-relaxed text-[var(--text-secondary)]">
                {text}
              </pre>
            )}
            {!textLoading && !textError && !text && (
              <p className="text-xs text-[var(--text-tertiary)]">No text content extracted from this document.</p>
            )}
          </div>
        )}

        {/* Structure tab */}
        {activeTab === 'structure' && (
          <div className="p-4">
            {outlineLoading && (
              <div className="space-y-2">
                <Skeleton className="h-3 w-1/2" />
                <Skeleton className="h-3 w-2/3" />
                <Skeleton className="h-3 w-1/3" />
              </div>
            )}
            {!outlineLoading && outlineError && (
              <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                <AlertCircle size={14} className="shrink-0 text-red-500" />
                <p className="text-xs text-red-700">{outlineError}</p>
              </div>
            )}
            {!outlineLoading && !outlineError && outline !== null && outline.length === 0 && (
              <div className="flex flex-col items-center gap-2 py-8 text-center">
                <p className="text-xs text-[var(--text-secondary)] font-medium">No structure available</p>
                <p className="text-[10px] text-[var(--text-tertiary)] max-w-xs">
                  {isIndexing
                    ? 'The document is still being indexed. Check back shortly.'
                    : 'This document did not produce a navigable outline. Try viewing the rendered content instead.'}
                </p>
              </div>
            )}
            {!outlineLoading && !outlineError && outline && outline.length > 0 && (
              <div className="space-y-0.5">
                {outline.map((node) => (
                  <StructureNode key={node.node_id} projectId={projectId} docId={doc.id} node={node} />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
