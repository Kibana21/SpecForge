'use client'
/**
 * Inline amber banner shown in §1 UI Specification when a spec's screens are
 * blocked pending a Figma link. The user either pastes a Figma URL (triggers
 * a UI-only regen) or skips (sentinel '__none__' — UI spec marked TBD; no
 * regen).
 *
 * Wires through `api.frs.setFigmaLink`. The parent's `onChanged` callback is
 * invoked after a successful response so it can re-fetch the FRS detail.
 */
import { useState } from 'react'
import { AlertTriangle, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { api } from '@/lib/api'

const SKIP_SENTINEL = '__none__'

interface Props {
  projectId: string
  specRowKey: string
  /** Existing screen sentinel state (so we can show "Replace link" affordance differently). */
  hasSentinel?: boolean
  /** Called after a successful link set (real or skipped). */
  onChanged: () => void
}

export function FigmaLinkPrompt({ projectId, specRowKey, hasSentinel, onChanged }: Props) {
  const [link, setLink] = useState('')
  const [busy, setBusy] = useState<'real' | 'skip' | null>(null)

  async function submit(linkValue: string) {
    setBusy(linkValue === SKIP_SENTINEL ? 'skip' : 'real')
    try {
      await api.frs.setFigmaLink(projectId, specRowKey, { link: linkValue })
      toast.success(
        linkValue === SKIP_SENTINEL
          ? 'Skipped — UI spec marked TBD'
          : 'Regenerating UI spec…',
      )
      onChanged()
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to set Figma link')
    } finally {
      setBusy(null)
    }
  }

  const linkLooksValid = /^https?:\/\/(?:[a-z]+\.)?figma\.com\//i.test(link.trim())

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50/70 p-4">
      <div className="flex items-start gap-2">
        <AlertTriangle size={16} className="text-amber-600 shrink-0 mt-0.5" />
        <div className="flex-1">
          <p className="text-sm font-semibold text-amber-900">
            {hasSentinel ? 'UI spec currently marked TBD' : 'Figma link required'}
          </p>
          <p className="text-xs text-amber-700 mt-1 leading-relaxed">
            {hasSentinel
              ? 'You skipped this UI spec earlier. Paste a Figma link to author the §1 UI Specification now — the AI will follow the design section by section.'
              : 'UI Specification cannot be authored until a Figma design link is provided. Once added, the AI will follow the design section by section.'}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        <input
          type="url"
          value={link}
          onChange={(e) => setLink(e.target.value)}
          placeholder="https://figma.com/file/.../node-id=…"
          className="flex-1 min-w-[200px] rounded-md border border-amber-300 bg-white px-3 py-1.5 text-sm font-mono"
          autoComplete="off"
          aria-label="Figma design URL"
        />
        <button
          onClick={() => submit(link.trim())}
          disabled={!linkLooksValid || busy !== null}
          className="inline-flex items-center gap-1.5 rounded-md bg-amber-600 text-white px-3 py-1.5 text-xs font-semibold hover:bg-amber-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {busy === 'real' ? <Loader2 size={12} className="animate-spin" /> : null}
          {busy === 'real' ? 'Saving…' : hasSentinel ? 'Replace link' : 'Add link'}
        </button>
        {!hasSentinel && (
          <button
            onClick={() => submit(SKIP_SENTINEL)}
            disabled={busy !== null}
            className="inline-flex items-center gap-1.5 rounded-md border border-amber-300 bg-white text-amber-700 px-3 py-1.5 text-xs hover:bg-amber-100 disabled:opacity-50 transition-colors"
          >
            {busy === 'skip' ? <Loader2 size={12} className="animate-spin" /> : null}
            {busy === 'skip' ? 'Skipping…' : 'Skip — UI TBD'}
          </button>
        )}
      </div>
      {link && !linkLooksValid && (
        <p className="mt-2 text-[10px] text-amber-700">
          That doesn&apos;t look like a Figma URL.
        </p>
      )}
    </div>
  )
}
