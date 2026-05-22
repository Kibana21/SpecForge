'use client'
import { useState } from 'react'
import { Zap } from 'lucide-react'
import clsx from 'clsx'
import { toast } from 'sonner'
import type { SpecType } from '@/lib/types'
import { api } from '@/lib/api'
import { Button } from '@/app/components/ui/button'

const STEPS: SpecType[] = ['functional', 'technical', 'user_stories', 'review']

interface GenerateSpecsButtonProps {
  projectId: string
  onGenerating: (tab: SpecType | null) => void
  onComplete: () => void
  disabled?: boolean
  disabledReason?: string
}

export function GenerateSpecsButton({ projectId, onGenerating, onComplete, disabled, disabledReason }: GenerateSpecsButtonProps) {
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
      toast.success('Specs generated', { description: 'Functional, technical, user stories & review are ready.' })
    } catch (err) {
      toast.error('Generation failed', { description: err instanceof Error ? err.message : 'Please try again.' })
    } finally {
      onGenerating(null)
      setRunning(false)
      onComplete()
    }
  }

  return (
    <Button onClick={run} disabled={running || disabled} title={disabled ? disabledReason : undefined}>
      <Zap size={14} className={clsx(running && 'animate-pulse')} />
      {running ? 'Generating…' : 'Generate Specs'}
    </Button>
  )
}
