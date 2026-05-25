'use client'
import { useState } from 'react'
import { Trash2, Plus, X, Building2 } from 'lucide-react'
import { toast } from 'sonner'
import useSWR from 'swr'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { Label } from '@/app/components/ui/label'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/app/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/app/components/ui/select'
import { ConfirmDialog } from '@/app/components/ConfirmDialog'
import { api } from '@/lib/api'
import type { AppInScope, AppListItem, ProjectPriority, ProjectRead, ProjectStatus } from '@/lib/types'

const PRIORITIES: ProjectPriority[] = ['low', 'medium', 'high', 'critical']
const STATUSES: ProjectStatus[] = ['draft', 'active', 'in_review', 'finalized', 'archived']

interface AppEntry {
  app_id: string
  name: string
  tier: number
  impact_note: string
}

interface Props {
  project: ProjectRead & { apps_in_scope?: AppInScope[] }
  canDelete: boolean
  onClose: () => void
  onUpdated: () => void
  onDeleted: () => void
}

export function EditProjectModal({ project, canDelete, onClose, onUpdated, onDeleted }: Props) {
  const [name, setName] = useState(project.name)
  const [description, setDescription] = useState(project.description ?? '')
  const [businessUnit, setBusinessUnit] = useState(project.business_unit ?? '')
  const [appScope, setAppScope] = useState(project.app_scope ?? '')
  const [priority, setPriority] = useState<ProjectPriority>(project.priority)
  const [status, setStatus] = useState<ProjectStatus>(project.status)
  const [goLive, setGoLive] = useState(project.go_live_date ?? '')
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [appSearch, setAppSearch] = useState('')
  const [showAppPicker, setShowAppPicker] = useState(false)

  // Build initial app entries from apps_in_scope
  const [appEntries, setAppEntries] = useState<AppEntry[]>(
    (project.apps_in_scope ?? [])
      .filter(a => a.included)
      .map(a => ({
        app_id: a.app_id,
        name: a.name,
        tier: a.tier,
        impact_note: (a as AppInScope & { impact_note?: string }).impact_note ?? '',
      }))
  )

  const { data: allApps } = useSWR<AppListItem[]>(
    showAppPicker ? '/api/apps-all' : null,
    () => api.apps.list(),
    { revalidateOnFocus: false }
  )

  const filtered = (allApps ?? []).filter(a =>
    !appEntries.find(e => e.app_id === a.id) &&
    (a.name.toLowerCase().includes(appSearch.toLowerCase()) ||
     a.short_name.toLowerCase().includes(appSearch.toLowerCase()))
  )

  function addApp(app: AppListItem) {
    setAppEntries(p => [...p, { app_id: app.id, name: app.name, tier: app.tier, impact_note: '' }])
    setAppSearch('')
  }

  function removeApp(appId: string) {
    setAppEntries(p => p.filter(e => e.app_id !== appId))
  }

  function updateNote(appId: string, note: string) {
    setAppEntries(p => p.map(e => e.app_id === appId ? { ...e, impact_note: note } : e))
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await api.projects.update(project.id, {
        name: name.trim(),
        description: description.trim(),
        business_unit: businessUnit.trim(),
        app_scope: appScope.trim(),
        priority, status,
        go_live_date: goLive || null,
        app_scope_entries: appEntries.map(e => ({ app_id: e.app_id, impact_note: e.impact_note || null })),
      } as Parameters<typeof api.projects.update>[1] & { app_scope_entries?: { app_id: string; impact_note: string | null }[] })
      toast.success('Project updated')
      onUpdated()
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Update failed')
      setSaving(false)
    }
  }

  async function handleDelete() {
    setDeleting(true)
    try {
      await api.projects.delete(project.id)
      toast.success('Project deleted')
      onDeleted()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed')
      setDeleting(false)
      setConfirmDelete(false)
    }
  }

  return (
    <>
      <Dialog open onOpenChange={(o) => !o && onClose()}>
        <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader><DialogTitle>Edit project</DialogTitle></DialogHeader>
          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="ep-name">Name</Label>
              <Input id="ep-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="ep-bu">Business unit</Label>
                <Input id="ep-bu" value={businessUnit} onChange={(e) => setBusinessUnit(e.target.value)} placeholder="Payments" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ep-app">Primary application</Label>
                <Input id="ep-app" value={appScope} onChange={(e) => setAppScope(e.target.value)} placeholder="PayHub" />
              </div>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div className="space-y-1.5">
                <Label>Priority</Label>
                <Select value={priority} onValueChange={(v) => setPriority(v as ProjectPriority)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{PRIORITIES.map((p) => <SelectItem key={p} value={p}>{p}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Status</Label>
                <Select value={status} onValueChange={(v) => setStatus(v as ProjectStatus)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{STATUSES.map((s) => <SelectItem key={s} value={s}>{s.replace('_', ' ')}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ep-golive">Go-live</Label>
                <Input id="ep-golive" type="date" value={goLive} onChange={(e) => setGoLive(e.target.value)} />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ep-desc">Description</Label>
              <textarea
                id="ep-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
                className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              />
            </div>

            {/* ── Impacted Applications ── */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="flex items-center gap-1.5">
                  <Building2 size={13} className="text-[var(--accent)]" />
                  Impacted Applications
                </Label>
                <button
                  type="button"
                  onClick={() => setShowAppPicker(p => !p)}
                  className="flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
                >
                  <Plus size={12} /> Add app
                </button>
              </div>

              {showAppPicker && (
                <div className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] p-3 space-y-2">
                  <Input
                    placeholder="Search apps…"
                    value={appSearch}
                    onChange={(e) => setAppSearch(e.target.value)}
                    className="h-8 text-sm"
                  />
                  <div className="max-h-36 overflow-y-auto space-y-1">
                    {filtered.slice(0, 15).map(app => (
                      <button
                        key={app.id}
                        type="button"
                        onClick={() => addApp(app)}
                        className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-xs hover:bg-[var(--bg-elevated)] transition-colors"
                      >
                        <span className="text-[10px] text-[var(--text-tertiary)] w-10 shrink-0">T{app.tier}</span>
                        <span className="font-medium text-[var(--text-primary)]">{app.name}</span>
                        <span className="text-[var(--text-tertiary)] text-[10px]">{app.short_name}</span>
                      </button>
                    ))}
                    {filtered.length === 0 && (
                      <p className="text-xs text-[var(--text-tertiary)] px-2 py-1">No apps found</p>
                    )}
                  </div>
                </div>
              )}

              {appEntries.length > 0 ? (
                <div className="space-y-2">
                  {appEntries.map(entry => (
                    <div key={entry.app_id} className="rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] p-3">
                      <div className="flex items-center justify-between mb-1.5">
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] text-[var(--text-tertiary)] font-medium">T{entry.tier}</span>
                          <span className="text-sm font-medium text-[var(--text-primary)]">{entry.name}</span>
                        </div>
                        <button
                          type="button"
                          onClick={() => removeApp(entry.app_id)}
                          className="text-[var(--text-tertiary)] hover:text-danger p-0.5 rounded"
                        >
                          <X size={12} />
                        </button>
                      </div>
                      <textarea
                        value={entry.impact_note}
                        onChange={(e) => updateNote(entry.app_id, e.target.value)}
                        rows={2}
                        placeholder="How does this initiative impact this app? (optional — used to ground AI generation)"
                        className="w-full resize-none rounded-md border border-[var(--border-subtle)] bg-[var(--bg-base)] px-2.5 py-1.5 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent)] placeholder:text-[var(--text-tertiary)]"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-[var(--text-tertiary)] px-1">
                  No apps in scope. Add apps to ground AI artifact generation in their documented capabilities.
                </p>
              )}
            </div>

            <DialogFooter className="flex items-center justify-between sm:justify-between">
              {canDelete ? (
                <Button type="button" variant="ghost" onClick={() => setConfirmDelete(true)}
                  className="text-danger hover:bg-danger-bg hover:text-danger">
                  <Trash2 size={14} /> Delete project
                </Button>
              ) : <span />}
              <div className="flex gap-2">
                <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
                <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save changes'}</Button>
              </div>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <ConfirmDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete "${project.name}"?`}
        description="This permanently removes the project and its sources, requirement understanding, and specs. This cannot be undone."
        confirmLabel="Delete project"
        danger
        loading={deleting}
        onConfirm={handleDelete}
      />
    </>
  )
}
