'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus, Layers } from 'lucide-react'
import { useProjects } from '@/lib/hooks/useProjects'
import { ProjectCard } from '@/app/components/ProjectCard'
import { NewProjectModal } from '@/app/components/NewProjectModal'
import { EmptyState } from '@/app/components/EmptyState'
import { Skeleton } from '@/app/components/Skeleton'

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
    <main className="min-h-screen">
      {/* Hero header */}
      <div className="border-b border-[var(--border-default)] bg-[var(--bg-surface)]">
        <div className="mx-auto max-w-6xl px-6 py-8">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2.5 mb-1">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent-blue)]">
                  <Layers size={16} className="text-white" />
                </div>
                <h1 className="text-xl font-bold text-[var(--text-primary)] tracking-tight">
                  SpecForge AI
                </h1>
              </div>
              <p className="text-sm text-[var(--text-secondary)] pl-10">
                Transform messy requirements into structured, versioned specs.
              </p>
            </div>
            <button
              onClick={() => setShowModal(true)}
              className="flex items-center gap-2 rounded-lg bg-[var(--accent-blue)] hover:bg-[var(--accent-blue-hover)] px-4 py-2.5 text-sm font-semibold text-white transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)] focus:ring-offset-2"
            >
              <Plus size={15} strokeWidth={2.5} />
              New Project
            </button>
          </div>
        </div>
      </div>

      {/* Project grid */}
      <div className="mx-auto max-w-6xl px-6 py-8">
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
    </main>
  )
}
