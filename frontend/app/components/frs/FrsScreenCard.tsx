'use client'
/**
 * §1.1 Screen card — one per `frs_screens` row.
 *
 * Layout: header with screen name + figma link badge + per-row action cluster
 * (Edit / Lock / Trash), then collapsible body with Purpose / Layout /
 * Navigation / Interactive behavior. The Edit pencil opens `FrsRowEditDialog`
 * with the 8-field screen schema. Skip-sentinel (figma_link === '__none__')
 * renders a yellow "UI design TBD" chip and offers Replace-link.
 */
import { useState } from 'react'
import {
  ChevronDown, ChevronRight, ExternalLink, Lock, LockOpen, Pencil, Trash2,
} from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import { api } from '@/lib/api'
import type { FrsScreenRow } from '@/lib/types'
import { FrsRowEditDialog, type FrsRowField } from './FrsRowEditDialog'

const SKIP_SENTINEL = '__none__'

interface Props {
  projectId: string
  screen: FrsScreenRow
  /** Re-fetch the FRS detail after a mutation. */
  onMutate: () => void
  /** Optional handler to switch to the FigmaLinkPrompt (e.g. when user clicks "Replace link"). */
  onReplaceFigma?: (screenRowKey: string) => void
}

const SCREEN_FIELDS: FrsRowField[] = [
  { name: 'screen_name', label: 'Screen name', type: 'text' },
  { name: 'figma_link', label: 'Figma link', type: 'text',
    placeholder: 'https://figma.com/file/… or __none__ to skip' },
  { name: 'purpose', label: 'Purpose', type: 'textarea', rows: 4 },
  { name: 'user_roles', label: 'User roles', type: 'tags',
    placeholder: 'Customer, Operator' },
  { name: 'layout', label: 'Layout', type: 'textarea', rows: 4 },
  { name: 'navigation', label: 'Navigation', type: 'textarea', rows: 3 },
  { name: 'interactive_behavior', label: 'Interactive behavior', type: 'textarea', rows: 4 },
]

export function FrsScreenCard({ projectId, screen, onMutate, onReplaceFigma }: Props) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [busy, setBusy] = useState(false)

  const skipped = screen.figma_link === SKIP_SENTINEL
  const hasRealLink = !!screen.figma_link && !skipped

  async function handleLockToggle() {
    setBusy(true)
    try {
      if (screen.is_locked) {
        await api.frs.unlockRow(projectId, 'frs_screens', screen.id)
        toast.success('Unlocked')
      } else {
        await api.frs.editRow(projectId, 'frs_screens', screen.id, {
          screen_name: screen.screen_name,
          figma_link: screen.figma_link,
          purpose: screen.purpose,
          user_roles: screen.user_roles,
          layout: screen.layout,
          navigation: screen.navigation,
          interactive_behavior: screen.interactive_behavior,
        }, { lock: true })
        toast.success('Locked')
      }
      onMutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Lock failed')
    } finally {
      setBusy(false)
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete screen "${screen.screen_name}"?\n\nIt will be soft-deleted (regeneration may re-create it).`)) return
    setBusy(true)
    try {
      await api.frs.deleteRow(projectId, 'frs_screens', screen.id)
      toast.success('Removed')
      onMutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className={cn(
        'group rounded-xl border bg-[var(--bg-surface)] transition-colors',
        screen.is_locked
          ? 'border-amber-200 ring-1 ring-amber-100/70'
          : 'border-[var(--border-default)] hover:border-[var(--accent)]/40',
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2.5 border-b border-[var(--border-subtle)]">
        <button
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 rounded p-0.5 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] transition-colors"
          aria-label={open ? 'Collapse screen' : 'Expand screen'}
          aria-expanded={open}
        >
          {open ? <ChevronDown size={13} /> : <ChevronRight size={13} />}
        </button>
        <p className="flex-1 text-sm font-semibold text-[var(--text-primary)] truncate">
          {screen.screen_name}
        </p>
        {/* Figma badge */}
        {skipped ? (
          <button
            onClick={() => onReplaceFigma?.(screen.row_key)}
            className="inline-flex items-center gap-1 text-[10px] font-semibold rounded px-1.5 py-0.5 border border-yellow-300 bg-yellow-50 text-yellow-800 hover:bg-yellow-100 transition-colors"
            title="Click to provide a Figma link now"
          >
            UI design TBD
          </button>
        ) : hasRealLink ? (
          <a
            href={screen.figma_link!}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1 text-[10px] rounded px-1.5 py-0.5 border border-violet-200 bg-violet-50 text-violet-700 hover:bg-violet-100 transition-colors"
            title={screen.figma_link!}
          >
            Figma <ExternalLink size={9} />
          </a>
        ) : null}
        {/* Action cluster */}
        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 focus-within:opacity-100 transition-opacity">
          <IconBtn label="Edit" onClick={() => setEditing(true)} disabled={busy}>
            <Pencil size={11} />
          </IconBtn>
          <IconBtn
            label={screen.is_locked ? 'Unlock' : 'Lock'}
            onClick={handleLockToggle}
            disabled={busy}
          >
            {screen.is_locked
              ? <LockOpen size={11} className="text-amber-600" />
              : <Lock size={11} />}
          </IconBtn>
          <IconBtn label="Delete" onClick={handleDelete} disabled={busy} danger>
            <Trash2 size={11} />
          </IconBtn>
        </div>
      </div>

      {/* Body */}
      {open && (
        <div className="px-3 py-2.5 space-y-2 text-xs">
          {screen.purpose && (
            <FieldRow label="Purpose" value={screen.purpose} />
          )}
          {screen.user_roles?.length > 0 && (
            <FieldRow label="User roles" value={screen.user_roles.join(', ')} />
          )}
          {screen.layout && (
            <FieldRow label="Layout" value={screen.layout} multiline />
          )}
          {screen.navigation && (
            <FieldRow label="Navigation" value={screen.navigation} multiline />
          )}
          {screen.interactive_behavior && (
            <FieldRow
              label="Interactive behavior"
              value={screen.interactive_behavior}
              multiline
            />
          )}
        </div>
      )}

      {editing && (
        <FrsRowEditDialog
          open
          title={`Edit screen — ${screen.screen_name}`}
          projectId={projectId}
          table="frs_screens"
          rowId={screen.id}
          initialValues={{
            screen_name: screen.screen_name,
            figma_link: screen.figma_link ?? '',
            purpose: screen.purpose,
            user_roles: screen.user_roles,
            layout: screen.layout,
            navigation: screen.navigation,
            interactive_behavior: screen.interactive_behavior,
          }}
          fields={SCREEN_FIELDS}
          isLocked={screen.is_locked}
          onClose={() => setEditing(false)}
          onSaved={() => { setEditing(false); onMutate() }}
        />
      )}
    </div>
  )
}

// ─── Sub-components ──────────────────────────────────────────────────────────

function FieldRow({ label, value, multiline }: { label: string; value: string; multiline?: boolean }) {
  return (
    <div className="grid grid-cols-[110px,1fr] gap-2">
      <span className="text-[10px] uppercase tracking-wide text-[var(--text-tertiary)] font-semibold pt-0.5">
        {label}
      </span>
      <span className={cn(
        'text-[var(--text-secondary)] leading-relaxed',
        multiline ? 'whitespace-pre-line' : 'truncate',
      )}>
        {value}
      </span>
    </div>
  )
}

function IconBtn({
  label, onClick, danger, disabled, children,
}: {
  label: string
  onClick: () => void
  danger?: boolean
  disabled?: boolean
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
