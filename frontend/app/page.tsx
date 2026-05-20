'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus } from 'lucide-react'
import { useProjects } from '@/lib/hooks/useProjects'
import { ProjectCard } from '@/app/components/ProjectCard'
import { NewProjectModal } from '@/app/components/NewProjectModal'
import { EmptyState } from '@/app/components/EmptyState'
import { Skeleton } from '@/app/components/Skeleton'
import { UserMenu } from '@/app/components/UserMenu'
import { AppShell } from '@/app/components/AppShell'
import { Layers } from 'lucide-react'

export default function DashboardPage() {
  const { projects, isLoading, mutate } = useProjects()
  const [showModal, setShowModal] = useState(false)
  const router = useRouter()

  function handleCreated(id: string) {
    setShowModal(false)
    mutate()
    router.push(`/projects/${id}`)
  }

  return (
    <AppShell>
      {/* Topbar */}
      <div className="shrink-0 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-[var(--text-primary)] tracking-tight">Projects</h2>
            <p className="text-xs text-[var(--text-secondary)]">
              Transform messy requirements into structured, versioned specs.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] hover:bg-[var(--accent-blue-hover)] px-4 py-2 text-sm font-semibold text-white transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)] focus:ring-offset-2"
            >
              <Plus size={15} strokeWidth={2.5} />
              New Project
            </button>
            <UserMenu />
          </div>
        </div>
      </div>

      {/* Project grid */}
      <div className="flex-1 overflow-y-auto px-6 py-6">
        {isLoading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-36 rounded-xl" />
            ))}
          </div>
        ) : projects.length === 0 ? (
          <div className="rounded-2xl border-2 border-dashed border-[var(--border-default)] bg-[var(--bg-surface)]">
            <EmptyState
              icon={<Layers size={40} strokeWidth={1.2} className="text-[var(--accent-blue)]" />}
              title="No projects yet"
              description="Create your first project to start transforming requirements into structured specs."
              action={
                <button
                  onClick={() => setShowModal(true)}
                  className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] hover:bg-[var(--accent-blue-hover)] px-4 py-2 text-sm font-semibold text-white transition-colors"
                >
                  <Plus size={14} />
                  New Project
                </button>
              }
            />
          </div>
        ) : (
          <>
            <p className="text-xs font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-4">
              {projects.length} {projects.length === 1 ? 'Project' : 'Projects'}
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <ProjectCard key={p.id} project={p} />
              ))}
            </div>
          </>
        )}
      </div>

      {showModal && (
        <NewProjectModal onClose={() => setShowModal(false)} onCreated={handleCreated} />
      )}
    </AppShell>
  )
}
