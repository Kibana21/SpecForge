'use client'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { Button } from '@/app/components/ui/button'

interface Props {
  total: number
  limit: number
  offset: number
  onChange: (offset: number) => void
}

export function Pagination({ total, limit, offset, onChange }: Props) {
  if (total === 0) return null
  const from = offset + 1
  const to = Math.min(offset + limit, total)
  const canPrev = offset > 0
  const canNext = offset + limit < total
  return (
    <div className="flex items-center justify-between pt-3 text-xs text-[var(--text-secondary)]">
      <span>
        Showing <strong className="text-[var(--text-primary)]">{from}–{to}</strong> of{' '}
        <strong className="text-[var(--text-primary)]">{total}</strong>
      </span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" disabled={!canPrev} onClick={() => onChange(Math.max(0, offset - limit))}>
          <ChevronLeft size={14} /> Prev
        </Button>
        <Button variant="outline" size="sm" disabled={!canNext} onClick={() => onChange(offset + limit)}>
          Next <ChevronRight size={14} />
        </Button>
      </div>
    </div>
  )
}
