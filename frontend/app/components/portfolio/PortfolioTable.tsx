'use client'
import { useRouter } from 'next/navigation'
import { MessageSquareWarning } from 'lucide-react'
import { Badge } from '@/app/components/ui/badge'
import type { ProjectListItem } from '@/lib/types'
import { PRIORITY_VARIANT, STATUS_LABEL, STATUS_VARIANT, currentStage } from '@/lib/ui/project'

export function PortfolioTable({ projects }: { projects: ProjectListItem[] }) {
  const router = useRouter()
  return (
    <div className="overflow-x-auto rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)]">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-[var(--border-default)] text-left text-[11px] uppercase tracking-wider text-[var(--text-tertiary)]">
            <th className="px-3 py-2.5 font-semibold">ID</th>
            <th className="px-3 py-2.5 font-semibold">Project</th>
            <th className="px-3 py-2.5 font-semibold">Business unit</th>
            <th className="px-3 py-2.5 font-semibold">Stage</th>
            <th className="px-3 py-2.5 font-semibold">Status</th>
            <th className="px-3 py-2.5 font-semibold">Priority</th>
            <th className="px-3 py-2.5 font-semibold text-center">Reviews</th>
            <th className="px-3 py-2.5 font-semibold">Updated</th>
          </tr>
        </thead>
        <tbody>
          {projects.map((p) => (
            <tr
              key={p.id}
              onClick={() => router.push(`/projects/${p.id}`)}
              className="cursor-pointer border-b border-[var(--border-subtle)] last:border-0 hover:bg-[var(--bg-elevated)] transition-colors"
            >
              <td className="px-3 py-2.5 font-mono text-[11px] text-[var(--text-tertiary)] whitespace-nowrap">
                {p.human_id ?? '—'}
              </td>
              <td className="px-3 py-2.5">
                <div className="flex items-center gap-2 font-medium text-[var(--text-primary)]">
                  <span className="truncate max-w-[260px]">{p.name}</span>
                  {p.is_stale && <Badge variant="danger">stale</Badge>}
                </div>
              </td>
              <td className="px-3 py-2.5 text-[var(--text-secondary)]">{p.business_unit ?? '—'}</td>
              <td className="px-3 py-2.5 text-[var(--text-secondary)] text-xs">{currentStage(p)}</td>
              <td className="px-3 py-2.5"><Badge variant={STATUS_VARIANT[p.status]}>{STATUS_LABEL[p.status]}</Badge></td>
              <td className="px-3 py-2.5"><Badge variant={PRIORITY_VARIANT[p.priority]}>{p.priority}</Badge></td>
              <td className="px-3 py-2.5 text-center">
                {p.open_review_count > 0 ? (
                  <span className="inline-flex items-center gap-1 text-xs text-warning">
                    <MessageSquareWarning size={13} /> {p.open_review_count}
                  </span>
                ) : (
                  <span className="text-[var(--text-tertiary)]">—</span>
                )}
              </td>
              <td className="px-3 py-2.5 text-xs text-[var(--text-tertiary)] whitespace-nowrap">
                {new Date(p.updated_at).toLocaleDateString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
