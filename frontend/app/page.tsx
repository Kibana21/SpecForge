'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { Plus } from 'lucide-react'
import { useProjects } from '@/lib/hooks/useProjects'
import { Button } from '@/app/components/ui/button'
import { Stagger, StaggerItem } from '@/app/components/motion/motion'
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
      {/* Hero topbar */}
      <div className="shrink-0 relative overflow-hidden border-b border-[var(--border-default)] px-6 py-6">
        <div className="pointer-events-none absolute inset-0 bg-gradient-to-br from-[var(--accent-subtle)] to-transparent opacity-70" />
        <div className="relative flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--accent-deep)]">Workspace</p>
            <h2 className="mt-1 text-2xl font-bold text-[var(--text-primary)] tracking-tight">Projects</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Transform messy requirements into structured, versioned specs.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button onClick={() => setShowModal(true)}>
              <Plus size={15} strokeWidth={2.5} />
              New Project
            </Button>
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
              icon={<Layers size={40} strokeWidth={1.2} className="text-[var(--accent)]" />}
              title="No projects yet"
              description="Create your first project to start transforming requirements into structured specs."
              action={
                <Button onClick={() => setShowModal(true)}>
                  <Plus size={14} />
                  New Project
                </Button>
              }
            />
          </div>
        ) : (
          <>
            <p className="text-xs font-semibold uppercase tracking-widest text-[var(--text-tertiary)] mb-4">
              {projects.length} {projects.length === 1 ? 'Project' : 'Projects'}
            </p>
            <Stagger className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {projects.map((p) => (
                <StaggerItem key={p.id}>
                  <ProjectCard project={p} />
                </StaggerItem>
              ))}
            </Stagger>
          </>
        )}
      </div>

      {showModal && (
        <NewProjectModal onClose={() => setShowModal(false)} onCreated={handleCreated} />
      )}
    </AppShell>
  )
}
