'use client'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { Badge } from '@/app/components/ui/badge'
import type { ProjectListItem, ProjectStatus } from '@/lib/types'
import { PRIORITY_VARIANT, STATUS_LABEL } from '@/lib/ui/project'

const LANES: ProjectStatus[] = ['draft', 'active', 'in_review', 'finalized']

export function PortfolioBoard({ projects }: { projects: ProjectListItem[] }) {
  const router = useRouter()
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
      {LANES.map((lane) => {
        const items = projects.filter((p) => p.status === lane)
        return (
          <div key={lane} className="rounded-xl border border-[var(--border-default)] bg-[var(--bg-base)] p-2">
            <div className="flex items-center justify-between px-1 pb-2">
              <span className="text-xs font-semibold text-[var(--text-secondary)]">{STATUS_LABEL[lane]}</span>
              <span className="text-[11px] text-[var(--text-tertiary)]">{items.length}</span>
            </div>
            <div className="space-y-2">
              {items.map((p) => (
                <motion.button
                  key={p.id}
                  whileHover={{ y: -2 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 28 }}
                  onClick={() => router.push(`/projects/${p.id}`)}
                  className="card card-hover w-full text-left p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] text-[var(--text-tertiary)]">{p.human_id ?? '—'}</span>
                    <Badge variant={PRIORITY_VARIANT[p.priority]}>{p.priority}</Badge>
                  </div>
                  <p className="mt-1 text-sm font-medium text-[var(--text-primary)] line-clamp-2">{p.name}</p>
                  <p className="mt-1 text-[11px] text-[var(--text-tertiary)]">{p.business_unit ?? '—'}</p>
                </motion.button>
              ))}
              {items.length === 0 && (
                <p className="px-1 py-4 text-center text-[11px] text-[var(--text-tertiary)]">No projects</p>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
