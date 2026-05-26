'use client'
import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { ArrowLeft, ArrowRight, Check, Sparkles, X, Brain } from 'lucide-react'
import { toast } from 'sonner'
import { AppShell } from '@/app/components/AppShell'
import { Button } from '@/app/components/ui/button'
import { Input } from '@/app/components/ui/input'
import { Badge } from '@/app/components/ui/badge'
import { api } from '@/lib/api'
import type { AppSuggestion } from '@/lib/types'

const STEPS = ['Identity', 'Apps in scope', 'Review']

export default function NewProjectWizard() {
  const router = useRouter()
  const [step, setStep] = useState(0)
  const [busy, setBusy] = useState(false)

  const [name, setName] = useState('')
  const [businessUnit, setBusinessUnit] = useState('')
  const [appScope, setAppScope] = useState('')
  const [description, setDescription] = useState('')

  const [suggestions, setSuggestions] = useState<AppSuggestion[]>([])
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [loadingApps, setLoadingApps] = useState(false)

  const identityValid = name.trim() && businessUnit.trim() && appScope.trim()

  async function loadSuggestions() {
    setLoadingApps(true)
    try {
      const q = [name, description, businessUnit, appScope].filter(Boolean).join(' ')
      const apps = await api.apps.suggest({ q })
      setSuggestions(apps)
      setSelected(new Set(apps.filter((a) => a.suggested).map((a) => a.id)))
    } catch {
      setSuggestions([])
    } finally {
      setLoadingApps(false)
    }
  }

  function next() {
    if (step === 0) {
      if (!identityValid) { toast.error('Name, business unit, and application are required'); return }
      loadSuggestions()
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1))
  }

  function toggleApp(id: string) {
    setSelected((prev) => {
      const n = new Set(prev)
      n.has(id) ? n.delete(id) : n.add(id)
      return n
    })
  }

  async function create() {
    setBusy(true)
    try {
      const proj = await api.projects.create({
        name: name.trim(), description: description.trim() || undefined,
        business_unit: businessUnit.trim(), app_scope: appScope.trim(),
        app_ids: Array.from(selected),
      })
      toast.success('Project created')
      router.push(`/projects/${proj.id}?view=interview`)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to create project')
      setBusy(false)
    }
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full overflow-y-auto">
        <header className="shrink-0 flex items-center gap-3 border-b border-[var(--border-default)] px-4 sm:px-6 py-3">
          <button onClick={() => router.push('/')} className="p-1.5 rounded-lg text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)]" aria-label="Cancel">
            <X size={16} />
          </button>
          <h1 className="text-sm font-semibold text-[var(--text-primary)]">New Project</h1>
          <div className="ml-auto flex items-center gap-2">
            {STEPS.map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <span className={`flex h-6 w-6 items-center justify-center rounded-full text-[11px] font-semibold ${
                  i < step ? 'bg-[var(--accent)] text-white' : i === step ? 'bg-[var(--accent-subtle)] text-[var(--accent-deep)]' : 'bg-[var(--bg-elevated)] text-[var(--text-tertiary)]'
                }`}>{i < step ? <Check size={12} /> : i + 1}</span>
                <span className={`text-xs ${i === step ? 'text-[var(--text-primary)] font-medium' : 'text-[var(--text-tertiary)]'} hidden sm:inline`}>{s}</span>
                {i < STEPS.length - 1 && <span className="text-[var(--border-default)]">·</span>}
              </div>
            ))}
          </div>
        </header>

        <div className="flex-1 mx-auto w-full max-w-2xl px-4 py-6">
          {step === 0 && (
            <div className="space-y-4">
              <Field label="Project name *">
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. PayHub Settlement Modernization" />
              </Field>
              <Field label="Business unit *">
                <Input value={businessUnit} onChange={(e) => setBusinessUnit(e.target.value)} placeholder="e.g. Payments" />
              </Field>
              <Field label="Primary application / area *">
                <Input value={appScope} onChange={(e) => setAppScope(e.target.value)} placeholder="e.g. PayHub" />
              </Field>
              <Field label="Description">
                <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={4}
                  placeholder="Brief context for your team…"
                  className="w-full resize-none rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent)]" />
              </Field>
            </div>
          )}

          {step === 1 && (
            <div>
              <p className="mb-3 text-sm text-[var(--text-secondary)]">
                Select the applications this project touches. AI-suggested apps are pre-selected.
              </p>
              {loadingApps ? (
                <p className="text-sm text-[var(--text-tertiary)]">Finding relevant apps…</p>
              ) : suggestions.length === 0 ? (
                <p className="rounded-lg border border-dashed border-[var(--border-default)] p-4 text-sm text-[var(--text-tertiary)]">
                  No apps found in the registry. You can <button className="underline" onClick={() => window.open('/apps', '_blank')}>add apps</button> or continue without apps in scope.
                </p>
              ) : (
                <div className="space-y-2">
                  {suggestions.map((a) => (
                    <button key={a.id} onClick={() => toggleApp(a.id)}
                      className={`flex w-full items-center gap-3 rounded-lg border p-3 text-left transition-colors ${
                        selected.has(a.id) ? 'border-[var(--accent)] bg-[var(--accent-subtle)]' : 'border-[var(--border-default)] hover:bg-[var(--bg-elevated)]'}`}>
                      <span className={`flex h-5 w-5 shrink-0 items-center justify-center rounded border ${selected.has(a.id) ? 'border-[var(--accent)] bg-[var(--accent)] text-white' : 'border-[var(--border-default)]'}`}>
                        {selected.has(a.id) && <Check size={12} />}
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-sm font-medium text-[var(--text-primary)] truncate">{a.name}</span>
                          {a.suggested && <Badge variant="ai"><Sparkles size={10} /> suggested</Badge>}
                          {a.is_onboarded && <Badge variant="success"><Brain size={10} /> AI-grounded</Badge>}
                          {a.match_pct > 0 && <span className="text-[10px] text-[var(--text-tertiary)]">{a.match_pct}%</span>}
                        </div>
                        <p className="text-[11px] text-[var(--text-tertiary)] truncate">
                          Tier {a.tier}{a.is_onboarded ? ` · ${a.fact_count} facts · ${a.corpus_doc_count} docs` : ' · not yet onboarded in App Registry'}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )}
              <p className="mt-3 text-xs text-[var(--text-tertiary)]">{selected.size} selected</p>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-3">
              <Row k="Name" v={name} />
              <Row k="Business unit" v={businessUnit} />
              <Row k="Application" v={appScope} />
              <div className="flex gap-3 border-b border-[var(--border-subtle)] py-2">
                <span className="w-32 shrink-0 text-xs font-medium text-[var(--text-tertiary)]">Apps in scope</span>
                <div className="flex flex-col gap-1">
                  {selected.size === 0
                    ? <span className="text-sm text-[var(--text-tertiary)]">None</span>
                    : suggestions.filter(a => selected.has(a.id)).map(a => (
                        <span key={a.id} className="text-sm text-[var(--text-primary)]">
                          {a.name}
                          <span className="ml-1.5 text-[11px] text-[var(--text-tertiary)]">T{a.tier}</span>
                        </span>
                      ))
                  }
                </div>
              </div>
              <Row k="Description" v={description || '—'} />
              <p className="pt-2 text-sm text-[var(--text-secondary)]">
                Creating the project will let you upload sources and generate the Requirement Understanding.
              </p>
            </div>
          )}
        </div>

        <footer className="shrink-0 flex items-center justify-between border-t border-[var(--border-default)] px-4 sm:px-6 py-3">
          <Button variant="ghost" onClick={() => (step === 0 ? router.push('/') : setStep((s) => s - 1))}>
            <ArrowLeft size={15} /> {step === 0 ? 'Cancel' : 'Back'}
          </Button>
          {step < STEPS.length - 1 ? (
            <Button onClick={next} disabled={step === 0 && !identityValid}>Next <ArrowRight size={15} /></Button>
          ) : (
            <Button onClick={create} disabled={busy}><Sparkles size={15} /> Create & Generate</Button>
          )}
        </footer>
      </div>
    </AppShell>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-xs font-medium text-[var(--text-secondary)]">{label}</label>
      {children}
    </div>
  )
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex gap-3 border-b border-[var(--border-subtle)] py-2 last:border-0">
      <span className="w-32 shrink-0 text-xs font-medium text-[var(--text-tertiary)]">{k}</span>
      <span className="text-sm text-[var(--text-primary)]">{v}</span>
    </div>
  )
}
