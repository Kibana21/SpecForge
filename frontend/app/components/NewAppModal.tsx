'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/app/components/ui/select'

interface Props {
  onClose: () => void
  onCreated: () => void
}

function toSlug(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9-\s]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .slice(0, 50)
}

export function NewAppModal({ onClose, onCreated }: Props) {
  const router = useRouter()
  const [name, setName] = useState('')
  const [shortName, setShortName] = useState('')
  const [description, setDescription] = useState('')
  const [tier, setTier] = useState<1 | 2 | 3>(2)
  const [domainArea, setDomainArea] = useState('')
  const [version, setVersion] = useState('')
  const [ownerTeam, setOwnerTeam] = useState('')
  const [environments, setEnvironments] = useState<string[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  function toggleEnv(env: string) {
    setEnvironments((prev) => (prev.includes(env) ? prev.filter((e) => e !== env) : [...prev, env]))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const app = await api.apps.create({
        name,
        short_name: shortName,
        description: description || undefined,
        tier,
        domain_area: domainArea || undefined,
        version: version || undefined,
        owner_team: ownerTeam || undefined,
        environments,
      })
      toast.success('Application created', { description: name })
      onCreated()
      router.push(`/apps/${app.id}`)
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create app'
      setError(msg)
      toast.error('Could not create app', { description: msg })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Dialog open onOpenChange={(o) => { if (!o) onClose() }}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>New Application</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <p className="text-xs text-danger bg-danger-bg rounded px-3 py-2">{error}</p>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="app-name">Name</Label>
            <Input
              id="app-name"
              required
              value={name}
              onChange={(e) => {
                setName(e.target.value)
                if (!shortName) setShortName(toSlug(e.target.value))
              }}
              placeholder="PayHub"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-short">Short name</Label>
            <Input
              id="app-short"
              required
              value={shortName}
              onChange={(e) => setShortName(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, ''))}
              onBlur={(e) => setShortName(toSlug(e.target.value))}
              className="font-mono"
              placeholder="payhub"
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-desc">Description</Label>
            <Textarea
              id="app-desc"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className="resize-none"
            />
          </div>

          <div className="grid grid-cols-3 gap-3">
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
              <Label htmlFor="app-domain">Domain</Label>
              <Input id="app-domain" value={domainArea} onChange={(e) => setDomainArea(e.target.value)} placeholder="payments" />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="app-version">Version</Label>
              <Input id="app-version" value={version} onChange={(e) => setVersion(e.target.value)} placeholder="1.0.0" />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="app-owner-team">Owner team</Label>
            <Input id="app-owner-team" value={ownerTeam} onChange={(e) => setOwnerTeam(e.target.value)} placeholder="Payments Eng" />
          </div>

          <div className="space-y-1.5">
            <Label>Environments</Label>
            <div className="flex flex-wrap gap-2">
              {['Prod', 'UAT', 'DR', 'Staging', 'Dev'].map((env) => (
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

          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating…' : 'Create App'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
