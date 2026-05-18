'use client'
import { useRouter } from 'next/navigation'
import { FileText, Clock } from 'lucide-react'
import clsx from 'clsx'
import type { ProjectListItem, SpecType } from '@/lib/types'

const specBadge: Record<SpecType, string> = {
  functional:  'Functional',
  technical:   'Technical',
  user_stories:'User Stories',
  review:      'Review',
}

function relativeTime(iso: string) {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60_000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

export function ProjectCard({ project }: { project: ProjectListItem }) {
  const router = useRouter()

  return (
    <button
      onClick={() => router.push(`/projects/${project.id}`)}
      className={clsx(
        'w-full text-left rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)]',
        'p-5 shadow-sm hover:shadow-md hover:border-[var(--accent-blue)]',
        'transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)] focus:ring-offset-2 focus:ring-offset-[var(--bg-base)]'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold text-[var(--text-primary)] line-clamp-1 text-sm">{project.name}</h3>
        {project.latest_spec_type && (
          <span className="shrink-0 text-[10px] font-semibold bg-indigo-100 text-indigo-700 border border-indigo-300 rounded px-1.5 py-0.5">
            {specBadge[project.latest_spec_type]}
          </span>
        )}
      </div>

      {project.description && (
        <p className="mt-1.5 text-xs text-[var(--text-secondary)] line-clamp-2">{project.description}</p>
      )}

      <div className="mt-4 flex items-center gap-3 text-[var(--text-tertiary)]">
        <span className="flex items-center gap-1 text-[11px]">
          <FileText size={12} />
          {project.doc_count} {project.doc_count === 1 ? 'doc' : 'docs'}
        </span>
        <span className="flex items-center gap-1 text-[11px]">
          <Clock size={12} />
          {relativeTime(project.updated_at)}
        </span>
      </div>
    </button>
  )
}
