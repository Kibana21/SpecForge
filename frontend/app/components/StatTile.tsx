'use client'
import { useEffect, useState } from 'react'
import { animate, useReducedMotion } from 'framer-motion'
import type { LucideIcon } from 'lucide-react'
import { Card } from '@/app/components/ui/card'

type Tone = 'accent' | 'info' | 'warning' | 'success'

const TONE: Record<Tone, string> = {
  accent: 'bg-accent-subtle text-accent-deep',
  info: 'bg-info-bg text-info',
  warning: 'bg-warning-bg text-warning',
  success: 'bg-success-bg text-success',
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
  icon: LucideIcon
  label: string
  value: string | number
  tone?: Tone
}

export function StatTile({ icon: Icon, label, value, tone = 'accent' }: Props) {
  return (
    <Card className="p-4 flex items-center gap-3 shadow-card">
      <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${TONE[tone]}`}>
        <Icon size={18} strokeWidth={2} />
      </div>
      <div className="min-w-0">
        <p className="text-xl font-bold leading-none text-[var(--text-primary)]">
          {typeof value === 'number' ? <CountUp value={value} /> : value}
        </p>
        <p className="mt-1 text-[11px] text-[var(--text-tertiary)] truncate">{label}</p>
      </div>
    </Card>
  )
}
