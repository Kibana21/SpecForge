'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, BookOpen, Brain, Database, List, Pencil, Plug } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { AppShell } from '@/app/components/AppShell'
import { EditAppModal } from '@/app/components/EditAppModal'
import { CorpusManager } from '@/app/components/CorpusManager'
import { FactList } from '@/app/components/FactList'
import { AskPanel } from '@/app/components/AskPanel'
import { IndexStatusBadge } from '@/app/components/IndexStatusBadge'
import { Skeleton } from '@/app/components/Skeleton'
import { useApp } from '@/lib/hooks/useApp'
import { useAuth } from '@/lib/auth/AuthContext'

type SectionKey = 'overview' | 'facts' | 'corpus' | 'pipeline' | 'ask'

const SECTIONS: { key: SectionKey; label: string; icon: LucideIcon }[] = [
  { key: 'overview', label: 'Overview', icon: BookOpen },
  { key: 'facts', label: 'Facts', icon: List },
  { key: 'corpus', label: 'Corpus', icon: Database },
  { key: 'pipeline', label: 'Pipeline', icon: Plug },
  { key: 'ask', label: 'Ask Brain', icon: Brain },
]

const TIER_LABEL: Record<number, string> = { 1: 'Tier 1', 2: 'Tier 2', 3: 'Tier 3' }

export default function AppDetailPage({ params }: { params: { id: string } }) {
  const router = useRouter()
  const { user } = useAuth()
  const { app, isLoading, mutate } = useApp(params.id)
  const [activeSection, setActiveSection] = useState<SectionKey>('overview')
  const [editing, setEditing] = useState(false)

  const isAdmin = user?.role === 'platform_admin'

  if (isLoading || !app) {
    return (
      <AppShell>
        <div className="p-6 space-y-3">
          <Skeleton className="h-4 w-64" />
          <Skeleton className="h-4 w-40" />
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col md:flex-row h-full overflow-hidden">
        {/* Left shelf nav (horizontal tab strip on mobile, vertical shelf on md+) */}
        <aside className="md:w-48 md:shrink-0 border-b md:border-b-0 md:border-r border-[var(--border-default)] flex flex-col bg-[var(--bg-surface)]">
          <div className="px-3 py-3 md:border-b border-[var(--border-subtle)]">
            <button
              onClick={() => router.push('/apps')}
              className="flex items-center gap-1.5 text-xs text-[var(--text-tertiary)] hover:text-[var(--text-primary)] mb-2"
            >
              <ArrowLeft size={12} />
              App Registry
            </button>
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-xs font-semibold text-[var(--text-primary)] truncate">{app.name}</h2>
              {isAdmin && (
                <button
                  onClick={() => setEditing(true)}
                  title="Edit application"
                  className="shrink-0 rounded-md p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
                >
                  <Pencil size={13} />
                </button>
              )}
            </div>
            <p className="text-[10px] font-mono text-[var(--text-tertiary)]">{app.short_name}</p>
          </div>
          <nav className="flex md:flex-col md:flex-1 gap-1 md:gap-0.5 px-2 pb-2 md:py-2 overflow-x-auto md:overflow-visible">
            {SECTIONS.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveSection(key)}
                className={`relative shrink-0 md:w-full flex items-center gap-2 rounded-lg px-2.5 py-2 text-xs transition-colors ${
                  activeSection === key
                    ? 'bg-[var(--accent-subtle)] text-[var(--accent-deep)] font-semibold'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                }`}
              >
                {activeSection === key && (
                  <span className="hidden md:block absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-full bg-[var(--accent)]" />
                )}
                <Icon size={13} className={activeSection === key ? 'text-[var(--accent)]' : ''} />
                {label}
              </button>
            ))}
          </nav>
        </aside>

        {/* Main content */}
        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          {activeSection === 'overview' && (
            <div className="max-w-2xl space-y-6">
              <div>
                <h1 className="text-lg font-semibold text-[var(--text-primary)]">{app.name}</h1>
                {app.description && (
                  <p className="text-sm text-[var(--text-secondary)] mt-1">{app.description}</p>
                )}
              </div>

              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
                {[
                  { label: 'Short Name', value: app.short_name, mono: true },
                  { label: 'Tier', value: TIER_LABEL[app.tier] ?? `Tier ${app.tier}` },
                  { label: 'Domain', value: app.domain_area ?? '—' },
                  { label: 'Version', value: app.version ?? '—' },
                  { label: 'Onboarded', value: app.is_onboarded ? 'Yes' : 'No' },
                ].map(({ label, value, mono }) => (
                  <div key={label}>
                    <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">{label}</p>
                    <p className={`text-sm text-[var(--text-primary)] mt-0.5 ${mono ? 'font-mono' : ''}`}>{value}</p>
                  </div>
                ))}
              </div>

              <div className="rounded-lg border border-[var(--border-default)] divide-y divide-[var(--border-subtle)]">
                {[
                  { label: 'Documents', value: `${app.pipeline_summary.total_docs} (${app.pipeline_summary.indexed_docs} indexed)` },
                  { label: 'Chunks', value: String(app.pipeline_summary.total_chunks) },
                  { label: 'Active Facts', value: String(app.facts.filter(f => f.status === 'active').length) },
                  { label: 'Last Indexed', value: app.pipeline_summary.last_indexed_at ? new Date(app.pipeline_summary.last_indexed_at).toLocaleString() : 'Never' },
                ].map(({ label, value }) => (
                  <div key={label} className="flex items-center justify-between px-4 py-2.5">
                    <span className="text-xs text-[var(--text-secondary)]">{label}</span>
                    <span className="text-xs font-medium text-[var(--text-primary)]">{value}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {activeSection === 'facts' && (
            <div className="max-w-2xl">
              <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
                Facts ({app.facts.filter(f => f.status === 'active').length})
              </h2>
              <FactList facts={app.facts} />
            </div>
          )}

          {activeSection === 'corpus' && (
            <div className="max-w-2xl">
              <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">
                Corpus Documents ({app.corpus_docs.length})
              </h2>
              <CorpusManager
                appId={app.id}
                docs={app.corpus_docs}
                canWrite={isAdmin}
                rebuildStatus={app.rebuild_status ?? null}
                onRefresh={() => mutate()}
              />
            </div>
          )}

          {activeSection === 'pipeline' && (
            <div className="max-w-2xl space-y-4">
              <h2 className="text-sm font-semibold text-[var(--text-primary)]">Pipeline Status</h2>
              {app.corpus_docs.length === 0 ? (
                <p className="text-xs text-[var(--text-tertiary)]">No corpus documents uploaded yet.</p>
              ) : (
                <div className="rounded-lg border border-[var(--border-default)] divide-y divide-[var(--border-subtle)]">
                  {app.corpus_docs.map((doc) => (
                    <div key={doc.id} className="px-4 py-3 flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-xs text-[var(--text-primary)] truncate">{doc.name}</p>
                        {doc.index_error && (
                          <p className="text-[10px] text-danger mt-0.5 truncate">{doc.index_error}</p>
                        )}
                      </div>
                      <IndexStatusBadge status={doc.index_status} />
                    </div>
                  ))}
                </div>
              )}
              <div className="rounded-lg border border-[var(--border-default)] p-4 space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Totals</p>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <p className="text-lg font-bold text-[var(--text-primary)]">{app.pipeline_summary.total_docs}</p>
                    <p className="text-[10px] text-[var(--text-tertiary)]">Documents</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-[var(--text-primary)]">{app.pipeline_summary.total_chunks}</p>
                    <p className="text-[10px] text-[var(--text-tertiary)]">Chunks</p>
                  </div>
                  <div>
                    <p className="text-lg font-bold text-[var(--text-primary)]">{app.pipeline_summary.indexed_docs}</p>
                    <p className="text-[10px] text-[var(--text-tertiary)]">Indexed</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeSection === 'ask' && (
            <div className="max-w-2xl">
              <h2 className="text-sm font-semibold text-[var(--text-primary)] mb-4">Ask the App Brain</h2>
              {app.pipeline_summary.indexed_docs === 0 ? (
                <p className="text-xs text-[var(--text-tertiary)]">
                  Upload and index corpus documents before asking questions.
                </p>
              ) : (
                <AskPanel appId={app.id} />
              )}
            </div>
          )}
        </div>
      </div>

      {editing && (
        <EditAppModal
          app={app}
          canDelete={isAdmin}
          onClose={() => setEditing(false)}
          onUpdated={() => mutate()}
          onDeleted={() => router.push('/apps')}
        />
      )}
    </AppShell>
  )
}
