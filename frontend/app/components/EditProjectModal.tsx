'use client'
import { useState } from 'react'
import { Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { Label } from '@/app/components/ui/label'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/app/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/app/components/ui/select'
import { ConfirmDialog } from '@/app/components/ConfirmDialog'
import { api } from '@/lib/api'
import type { ProjectPriority, ProjectRead, ProjectStatus } from '@/lib/types'

const PRIORITIES: ProjectPriority[] = ['low', 'medium', 'high', 'critical']
const STATUSES: ProjectStatus[] = ['draft', 'active', 'in_review', 'finalized', 'archived']

interface Props {
  project: ProjectRead
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
      })
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
        <DialogContent className="sm:max-w-lg">
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
