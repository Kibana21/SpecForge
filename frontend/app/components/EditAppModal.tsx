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
import type { AppDetail } from '@/lib/types'

const ALL_ENVS = ['Prod', 'UAT', 'DR', 'Staging', 'Dev']

interface Props {
  app: AppDetail
  canDelete: boolean
  onClose: () => void
  onUpdated: () => void
  onDeleted: () => void
}

export function EditAppModal({ app, canDelete, onClose, onUpdated, onDeleted }: Props) {
  const [name, setName] = useState(app.name)
  const [description, setDescription] = useState(app.description ?? '')
  const [tier, setTier] = useState<1 | 2 | 3>(app.tier as 1 | 2 | 3)
  const [domainArea, setDomainArea] = useState(app.domain_area ?? '')
  const [version, setVersion] = useState(app.version ?? '')
  const [ownerTeam, setOwnerTeam] = useState(app.owner_team ?? '')
  const [environments, setEnvironments] = useState<string[]>(app.environments ?? [])
  const [saving, setSaving] = useState(false)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [deleting, setDeleting] = useState(false)

  function toggleEnv(env: string) {
    setEnvironments((p) => (p.includes(env) ? p.filter((e) => e !== env) : [...p, env]))
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    setSaving(true)
    try {
      await api.apps.update(app.id, {
        name: name.trim(),
        description: description.trim() || undefined,
        tier,
        domain_area: domainArea.trim() || undefined,
        version: version.trim() || undefined,
        owner_team: ownerTeam.trim() || undefined,
        environments,
      })
      toast.success('Application updated')
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
      await api.apps.delete(app.id)
      toast.success('Application deleted')
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
          <DialogHeader>
            <DialogTitle>Edit application</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="edit-name">Name</Label>
              <Input id="edit-name" value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Tier</Label>
                <Select value={String(tier)} onValueChange={(v) => setTier(Number(v) as 1 | 2 | 3)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="1">Tier 1</SelectItem>
                    <SelectItem value="2">Tier 2</SelectItem>
                    <SelectItem value="3">Tier 3</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit-version">Version</Label>
                <Input id="edit-version" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="1.0.0" />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit-owner">Owner team</Label>
                <Input id="edit-owner" value={ownerTeam} onChange={(e) => setOwnerTeam(e.target.value)} placeholder="Payments Eng" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit-domain">Domain</Label>
                <Input id="edit-domain" value={domainArea} onChange={(e) => setDomainArea(e.target.value)} placeholder="payments" />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>Environments</Label>
              <div className="flex flex-wrap gap-2">
                {ALL_ENVS.map((env) => (
                  <button
                    key={env}
                    type="button"
                    onClick={() => toggleEnv(env)}
                    className={`rounded-lg border px-2.5 py-1 text-xs transition-colors ${
                      environments.includes(env)
                        ? 'border-[var(--accent)] bg-[var(--accent-subtle)] text-[var(--accent-deep)] font-medium'
                        : 'border-[var(--border-default)] text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]'
                    }`}
                  >
                    {env}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="edit-desc">Description</Label>
              <textarea
                id="edit-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
                className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]"
              />
            </div>

            <DialogFooter className="flex items-center justify-between sm:justify-between">
              {canDelete ? (
                <Button type="button" variant="ghost" onClick={() => setConfirmDelete(true)}
                  className="text-danger hover:bg-danger-bg hover:text-danger">
                  <Trash2 size={14} /> Delete app
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
        title={`Delete "${app.name}"?`}
        description="This permanently removes the app and its entire App Brain — corpus, facts, trees, and project links. This cannot be undone."
        confirmLabel="Delete app"
        danger
        loading={deleting}
        onConfirm={handleDelete}
      />
    </>
  )
}
