'use client'

import { useState } from 'react'
import { toast } from 'sonner'
import { Sparkles, Loader2, Undo2, Wand2 } from 'lucide-react'
import { api } from '@/lib/api'
import { NFR_CATEGORIES } from '@/lib/nfr-manifest'

interface Props {
  projectId: string
  brdValidated: boolean
  generating: boolean
  onGenerate: (brief: string) => void
}

/** NFR landing page (R-INTAKE): optional ad-hoc requirements + AI-enhance, then generate. */
export function NfrEmptyState({ projectId, brdValidated, generating, onGenerate }: Props) {
  const [brief, setBrief] = useState('')
  const [preEnhance, setPreEnhance] = useState<string | null>(null)
  const [enhancing, setEnhancing] = useState(false)

  async function enhance() {
    if (!brief.trim()) { toast.message('Type some requirements to enhance first.'); return }
    setEnhancing(true)
    try {
      const res = await api.nfr.enhance(projectId, { brief_text: brief })
      setPreEnhance(brief)
      setBrief(res.enhanced_brief)
      toast.success('Brief enhanced')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Enhance failed')
    } finally {
      setEnhancing(false)
    }
  }

  return (
    <div className="mx-auto max-w-2xl py-10">
      <h2 className="text-lg font-semibold text-[var(--text-primary)]">NFR Builder</h2>
      <p className="mt-1 text-sm text-[var(--text-secondary)]">
        Generate non-functional requirements across seven quality dimensions, each traceable to your validated BRD.
      </p>

      <div className="mt-4 flex flex-wrap gap-2">
        {NFR_CATEGORIES.map((c) => (
          <span key={c.key} className="inline-flex items-center gap-1 rounded-full border border-[var(--border-subtle)] px-2.5 py-1 text-xs text-[var(--text-secondary)]">
            {c.emoji} {c.label}
          </span>
        ))}
      </div>

      <div className="mt-6 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-4">
        <div className="mb-2 flex items-center justify-between">
          <label className="text-xs font-semibold text-[var(--text-secondary)]">Ad-hoc requirements <span className="font-normal text-[var(--text-tertiary)]">(optional)</span></label>
          <div className="flex items-center gap-2">
            {preEnhance !== null && (
              <button onClick={() => { setBrief(preEnhance); setPreEnhance(null) }}
                      className="inline-flex items-center gap-1 text-[11px] text-[var(--text-tertiary)] hover:text-[var(--text-primary)]">
                <Undo2 size={11} /> Undo
              </button>
            )}
            <button onClick={enhance} disabled={enhancing}
                    className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] px-2 py-1 text-[11px] text-[var(--accent-deep)] hover:bg-[var(--accent-subtle)]/40 disabled:opacity-50">
              {enhancing ? <Loader2 size={11} className="animate-spin" /> : <Sparkles size={11} />} AI Enhance
            </button>
          </div>
        </div>
        <textarea
          value={brief}
          onChange={(e) => setBrief(e.target.value)}
          rows={4}
          placeholder='Paste any quality requirements, standards, or constraints to fold in — e.g. "WCAG 2.2 AA · p99 < 800ms · SOC-2 audit logging". Leave blank to generate from the BRD alone.'
          className="w-full resize-none rounded-md border border-[var(--border-default)] bg-[var(--bg-elevated)] px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-[var(--accent-ring)]"
        />
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          disabled={!brdValidated || generating}
          onClick={() => onGenerate(brief)}
          className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {generating ? <Loader2 size={14} className="animate-spin" /> : <Wand2 size={14} />} Generate NFRs
        </button>
        {!brdValidated && <span className="text-xs text-[var(--text-tertiary)]">Unlocks once the BRD is validated.</span>}
      </div>
    </div>
  )
}
