'use client'
import { useState } from 'react'
import { toast } from 'sonner'
import { api } from '@/lib/api'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/app/components/ui/dialog'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { Textarea } from '@/app/components/ui/textarea'
import { Label } from '@/app/components/ui/label'

interface NewProjectModalProps {
  onClose: () => void
  onCreated: (id: string) => void
}

export function NewProjectModal({ onClose, onCreated }: NewProjectModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = name.trim()
    if (!trimmed) { setError('Project name is required.'); return }
    setLoading(true); setError('')
    try {
      const project = await api.projects.create({ name: trimmed, description: description.trim() || undefined })
      toast.success('Project created', { description: trimmed })
      onCreated(project.id)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to create project.'
      setError(msg)
      toast.error('Could not create project', { description: msg })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Project</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="project-name">
              Name <span className="text-danger">*</span>
            </Label>
            <Input
              id="project-name"
              autoFocus
              value={name}
              onChange={(e) => { setName(e.target.value); setError('') }}
              placeholder="e.g. Inventory Management System"
            />
            {error && <p className="text-xs text-danger">{error}</p>}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="project-desc">
              Description <span className="text-[var(--text-tertiary)] font-normal">(optional)</span>
            </Label>
            <Textarea
              id="project-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief context for your team…"
              rows={3}
              className="resize-none"
            />
          </div>

          <DialogFooter>
            <Button type="button" variant="ghost" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating…' : 'Create Project'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
