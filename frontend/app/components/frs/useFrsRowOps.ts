'use client'
/**
 * Shared hook for the Lock-toggle + Delete operations on any versioned FRS
 * row. Cards pass the row's id, table, current lock state, and a `fields`
 * payload for the lock-edit. Returns busy state + handlers.
 */
import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api'

interface Args {
  projectId: string
  table: string
  rowId: string
  isLocked: boolean
  /** Snapshot of the row's current fields — used when locking via api.frs.editRow. */
  lockPayload: Record<string, unknown>
  /** Human-readable name for the delete confirm dialog. */
  label: string
  onMutate: () => void
}

export function useFrsRowOps({
  projectId, table, rowId, isLocked, lockPayload, label, onMutate,
}: Args) {
  const [busy, setBusy] = useState(false)

  async function handleLockToggle() {
    setBusy(true)
    try {
      if (isLocked) {
        await api.frs.unlockRow(projectId, table, rowId)
        toast.success('Unlocked')
      } else {
        await api.frs.editRow(projectId, table, rowId, lockPayload, { lock: true })
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
    if (!confirm(`Delete ${label}?\n\nIt will be soft-deleted (regeneration may re-create it).`)) return
    setBusy(true)
    try {
      await api.frs.deleteRow(projectId, table, rowId)
      toast.success('Removed')
      onMutate()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Delete failed')
    } finally {
      setBusy(false)
    }
  }

  return { busy, handleLockToggle, handleDelete }
}
