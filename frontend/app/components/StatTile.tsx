'use client'
import { useEffect, useState } from 'react'
import { animate, useReducedMotion } from 'framer-motion'
import { Card } from '@/app/components/ui/card'

type Tone = 'default' | 'success' | 'info' | 'warning' | 'danger'

const VALUE_TONE: Record<Tone, string> = {
  default: 'text-[var(--text-primary)]',
  success: 'text-success',
  info: 'text-info',
  warning: 'text-warning',
  danger: 'text-danger',
}

function CountUp({ value }: { value: number }) {
  const reduce = useReducedMotion()
  const [display, setDisplay] = useState(reduce ? value : 0)
  useEffect(() => {
    if (reduce) { setDisplay(value); return }
    const controls = animate(0, value, {
      duration: 0.8,
      ease: [0.22, 1, 0.36, 1],
      onUpdate: (v) => setDisplay(Math.round(v)),
    })
    return () => controls.stop()
  }, [value, reduce])
  return <>{display}</>
}

interface Props {
  label: string
  /** numeric values animate with a count-up; pass null for an untracked placeholder */
  value: number | string | null
  sublabel?: string
  tone?: Tone
}

export function StatTile({ label, value, sublabel, tone = 'default' }: Props) {
  const isPlaceholder = value === null || value === undefined
  return (
    <Card
      className={`p-4 shadow-card ${tone === 'danger' && !isPlaceholder ? 'border-danger-border bg-danger-bg/40' : ''}`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">
        {label}
      </p>
      <p className={`mt-1.5 text-2xl font-bold leading-none ${isPlaceholder ? 'text-[var(--text-tertiary)]' : VALUE_TONE[tone]}`}>
        {isPlaceholder ? '—' : typeof value === 'number' ? <CountUp value={value} /> : value}
      </p>
      {sublabel && (
        <p className="mt-1.5 text-[11px] text-[var(--text-tertiary)] truncate">{sublabel}</p>
      )}
    </Card>
  )
}
