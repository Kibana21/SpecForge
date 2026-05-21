'use client'
import { Upload, Cpu, FileCode, CheckCircle } from 'lucide-react'
import clsx from 'clsx'

const steps = [
  { key: 'upload',   label: 'Upload',   icon: Upload },
  { key: 'extract',  label: 'Extract',  icon: Cpu },
  { key: 'generate', label: 'Generate', icon: FileCode },
  { key: 'review',   label: 'Review',   icon: CheckCircle },
] as const

type Step = (typeof steps)[number]['key']

export function WorkflowSteps({ current }: { current: Step }) {
  const currentIdx = steps.findIndex((s) => s.key === current)

  return (
    <div className="px-4 py-5">
      <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-tertiary)] mb-4">
        Workflow
      </p>
      <ol className="space-y-1">
        {steps.map((step, i) => {
          const done   = i < currentIdx
          const active = i === currentIdx
          const Icon   = step.icon
          return (
            <li key={step.key} className="flex items-center gap-3">
              <div
                className={clsx(
                  'flex h-7 w-7 shrink-0 items-center justify-center rounded-full border text-[11px] transition-colors',
                  done   && 'border-success-border bg-success-bg text-success',
                  active && 'border-accent bg-accent-subtle text-accent-deep',
                  !done && !active && 'border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'
                )}
              >
                <Icon size={13} strokeWidth={2} />
              </div>
              <span
                className={clsx(
                  'text-xs',
                  done   && 'text-success',
                  active && 'text-accent-deep font-semibold',
                  !done && !active && 'text-[var(--text-tertiary)]'
                )}
              >
                {step.label}
              </span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}
