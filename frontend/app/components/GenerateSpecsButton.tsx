'use client'
import { useState } from 'react'
import { Zap } from 'lucide-react'
import clsx from 'clsx'
import type { SpecType } from '@/lib/types'
import { api } from '@/lib/api'

const STEPS: SpecType[] = ['functional', 'technical', 'user_stories', 'review']

interface GenerateSpecsButtonProps {
  projectId: string
  onGenerating: (tab: SpecType | null) => void
  onComplete: () => void
}

export function GenerateSpecsButton({ projectId, onGenerating, onComplete }: GenerateSpecsButtonProps) {
  const [running, setRunning] = useState(false)

  async function run() {
    setRunning(true)
    try {
      for (const step of STEPS) {
        onGenerating(step)
        if (step === 'review') {
          await api.specs.review(projectId)
        } else {
          await api.specs.generate(projectId, step)
        }
      }
    } catch {
      // Surface error via onComplete so UI can refresh
    } finally {
      onGenerating(null)
      setRunning(false)
      onComplete()
    }
  }

  return (
    <button
      onClick={run}
      disabled={running}
      className={clsx(
        'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
        'bg-[var(--accent-blue)] hover:bg-[var(--accent-blue-hover)] text-white',
        'disabled:opacity-60 disabled:cursor-not-allowed'
      )}
    >
      <Zap size={14} className={clsx(running && 'animate-pulse')} />
      {running ? 'Generating…' : 'Generate Specs'}
    </button>
  )
}
