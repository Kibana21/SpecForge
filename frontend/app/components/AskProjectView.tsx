'use client'
/**
 * AskProjectView — two-pane shell for the Project Copilot.
 * Left: ProjectChatPanel (conversation + reasoning trail + input)
 * Right: EvidencePanel (live tree map, concepts, facts, grounding meter)
 * Owns shared trace + hoverToken state so both panes stay in sync.
 */
import { useState } from 'react'
import { ProjectChatPanel } from './ProjectChatPanel'
import { EvidencePanel } from './EvidencePanel'
import type { ProjectAskTrace } from '@/lib/types'

interface Props {
  projectId: string
}

export function AskProjectView({ projectId }: Props) {
  const [trace, setTrace] = useState<ProjectAskTrace | null>(null)
  const [hoverToken, setHoverToken] = useState<string | null>(null)

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_minmax(300px,38%)] gap-4" style={{ height: 'calc(100vh - 200px)' }}>
      <div className="min-h-0 overflow-hidden">
        <ProjectChatPanel
          projectId={projectId}
          onTrace={setTrace}
          hoverToken={hoverToken}
          onHoverToken={setHoverToken}
        />
      </div>
      <div className="min-h-0 hidden lg:block">
        <EvidencePanel
          projectId={projectId}
          trace={trace}
          hoverToken={hoverToken}
        />
      </div>
    </div>
  )
}
