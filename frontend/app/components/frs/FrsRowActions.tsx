'use client'
/**
 * Shared per-row action cluster used by every Stage B card. Same visual
 * language as Stage A's hover Edit/Lock/Delete pattern.
 */
import { Lock, LockOpen, Pencil, Trash2 } from 'lucide-react'
import { cn } from '@/lib/utils'

interface Props {
  isLocked: boolean
  busy?: boolean
  onEdit: () => void
  onLock: () => void
  onDelete: () => void
  /** Always-visible cluster (skip the opacity-on-hover behaviour). */
  alwaysVisible?: boolean
  /** Extra className on the wrapper. */
  className?: string
}

export function FrsRowActions({
  isLocked, busy, onEdit, onLock, onDelete, alwaysVisible, className,
}: Props) {
  return (
    <div
      className={cn(
        'shrink-0 flex items-center gap-0.5 transition-opacity',
        alwaysVisible ? '' : 'opacity-0 group-hover:opacity-100 focus-within:opacity-100',
        className,
      )}
    >
      <FrsIconButton label="Edit" onClick={onEdit} disabled={busy}>
        <Pencil size={11} />
      </FrsIconButton>
      <FrsIconButton
        label={isLocked ? 'Unlock' : 'Lock'}
        onClick={onLock}
        disabled={busy}
      >
        {isLocked
          ? <LockOpen size={11} className="text-amber-600" />
          : <Lock size={11} />}
      </FrsIconButton>
      <FrsIconButton label="Delete" onClick={onDelete} disabled={busy} danger>
        <Trash2 size={11} />
      </FrsIconButton>
    </div>
  )
}

export function FrsIconButton({
  label, onClick, disabled, danger, children,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
  danger?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      title={label}
      aria-label={label}
      className={cn(
        'rounded-md p-1 text-[var(--text-tertiary)] transition-colors disabled:opacity-40',
        danger
          ? 'hover:text-[var(--status-danger)] hover:bg-red-50'
          : 'hover:text-[var(--accent)] hover:bg-[var(--accent-subtle)]',
      )}
    >
      {children}
    </button>
  )
}
