'use client'

import { useMemo, useState } from 'react'
import useSWR from 'swr'
import { toast } from 'sonner'
import { ChevronLeft, Download, ShieldCheck } from 'lucide-react'
import { api } from '@/lib/api'
import type { NfrCategory, NfrDetail, NfrFindingsResponse } from '@/lib/types'
import { NFR_CATEGORY_LABEL } from '@/lib/nfr-manifest'
import { NfrEmptyState } from './NfrEmptyState'
import { NfrGenerationTheater } from './NfrGenerationTheater'
import { NfrCategoryRail, type NfrSection } from './NfrCategoryRail'
import { NfrRequirementTable } from './NfrRequirementTable'
import { NfrGovernancePanel } from './NfrGovernancePanel'
import { NfrQualityRadar } from './NfrQualityRadar'
import { NfrFindingsDrawer } from './NfrFindingsDrawer'
import type { BrdOption } from './NfrRowDialog'

interface Props {
  projectId: string
  onBack: () => void
}

export function NfrBuilderView({ projectId, onBack }: Props) {
  const { data: detail, mutate, isLoading } = useSWR<NfrDetail>(
    `nfr-detail-${projectId}`,
    () => api.nfr.get(projectId),
    {
      revalidateOnFocus: false,
      refreshInterval: (d) => {
        const s = d?.document?.status
        if (s === 'generating') return 1500
        if (d?.document?.unit_status?.['_current_unit']) return 1500
        return 0
      },
    },
  )
  const { data: brd } = useSWR(`brd-detail-${projectId}`, () => api.brd.get(projectId), { revalidateOnFocus: false })

  const [active, setActive] = useState<NfrSection>({ kind: 'category', key: 'performance' })
  const [findingsOpen, setFindingsOpen] = useState(false)
  const [findings, setFindings] = useState<NfrFindingsResponse | null>(null)
  const [generating, setGenerating] = useState(false)
  const [validating, setValidating] = useState(false)

  const brdOptions: BrdOption[] = useMemo(() => {
    const out: BrdOption[] = []
    const sections = (brd as { sections?: Record<string, Array<Record<string, unknown>>> } | undefined)?.sections ?? {}
    for (const o of sections['brd_objectives'] ?? [])
      out.push({ kind: 'brd_objective', ref: String(o.row_key), label: String(o.statement ?? '').slice(0, 60) })
    for (const b of sections['brd_business_requirements'] ?? [])
      out.push({ kind: 'brd_business_requirement', ref: String(b.row_key), label: String(b.title ?? '').slice(0, 60) })
    return out
  }, [brd])

  const status = detail?.document?.status ?? null
  const sections = detail?.sections ?? {}
  const hasDoc = !!detail?.document
  const isGenerating = status === 'generating' || !!detail?.document?.unit_status?.['_current_unit']

  async function handleGenerate(brief: string) {
    setGenerating(true)
    try {
      await api.nfr.generate(projectId, { brief: brief.trim() || undefined })
      await mutate()
      toast.success('NFRs generated')
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Generation failed')
    } finally {
      setGenerating(false)
    }
  }

  async function openFindings() {
    setFindingsOpen(true)
    try { setFindings(await api.nfr.findings(projectId)) } catch { /* noop */ }
  }

  async function handleValidate() {
    setValidating(true)
    try {
      const res = await api.nfr.validate(projectId)
      setFindings(res)
      if (res.ok) { toast.success('NFR validated ✓'); setFindingsOpen(false); await mutate() }
      else toast.error('Validation blocked — see findings')
    } catch (e) {
      // 409 returns findings in error details
      const det = (e as { details?: { findings?: NfrFindingsResponse['findings'] } })?.details
      if (det?.findings) setFindings({ ok: false, findings: det.findings })
      toast.error('Validation blocked — see findings')
    } finally {
      setValidating(false)
    }
  }

  if (isLoading) return <div className="p-8 text-sm text-[var(--text-tertiary)]">Loading…</div>

  if (!hasDoc || (Object.keys(sections).length === 0 && !isGenerating)) {
    return (
      <div className="flex h-full flex-col">
        <Header onBack={onBack} status={status}
                onValidate={openFindings} onExport={() => window.open(api.nfr.exportUrl(projectId), '_blank')} showActions={false} />
        <NfrEmptyState projectId={projectId} brdValidated generating={generating} onGenerate={handleGenerate} />
      </div>
    )
  }

  // Quality insight line for the radar panel.
  const reqs = sections['nfr_requirements'] ?? []
  const noMetric = reqs.filter((r) => !r.na && !(r.measurement && String(r.measurement).trim())).length
  const heaviest = (detail?.radar ?? []).reduce<{ category: NfrCategory; weighted: number } | null>(
    (top, a) => (!top || a.weighted > top.weighted ? { category: a.category, weighted: a.weighted } : top), null)

  return (
    <div className="flex h-full flex-col overflow-hidden bg-[var(--bg-base)]">
      <Header onBack={onBack} status={status}
              onValidate={openFindings} onExport={() => window.open(api.nfr.exportUrl(projectId), '_blank')} showActions />

      {isGenerating ? (
        <NfrGenerationTheater unitStatus={detail?.document?.unit_status ?? null} />
      ) : (
        <div className="flex flex-1 overflow-hidden">
          <NfrCategoryRail sections={sections} active={active} onPick={setActive} />

          <div className="flex-1 overflow-hidden p-4">
            {active.kind === 'category' ? (
              <NfrRequirementTable
                projectId={projectId} category={active.key}
                rows={reqs.filter((r) => r.category === active.key)}
                tracesBySource={detail?.traceability_by_source ?? {}}
                brdOptions={brdOptions} onMutate={() => mutate()}
              />
            ) : (
              <NfrGovernancePanel projectId={projectId} table={active.table}
                                  rows={sections[active.table] ?? []} onMutate={() => mutate()} />
            )}
          </div>

          {/* Persistent Quality Radar panel (the navigator + overview). */}
          {detail && (
            <aside className="hidden w-[300px] shrink-0 overflow-y-auto border-l border-[var(--border-default)] bg-[var(--bg-surface)] p-4 lg:block">
              <h3 className="mb-2 text-[10px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">Quality Radar</h3>
              <NfrQualityRadar
                radar={detail.radar}
                activeCategory={active.kind === 'category' ? active.key : null}
                onPick={(c: NfrCategory) => setActive({ kind: 'category', key: c })}
              />
              <div className="mt-3 space-y-1 border-t border-[var(--border-subtle)] pt-3 text-[11px] text-[var(--text-secondary)]">
                <div>{reqs.length} requirements across {new Set(reqs.map((r) => r.category)).size}/7 categories</div>
                {heaviest && heaviest.weighted > 0 && (
                  <div>Heaviest axis: <span className="font-medium text-[var(--text-primary)]">{NFR_CATEGORY_LABEL[heaviest.category]}</span></div>
                )}
                {noMetric > 0 && <div className="text-amber-600">{noMetric} NFR{noMetric > 1 ? 's' : ''} missing a measurement</div>}
              </div>
            </aside>
          )}
        </div>
      )}

      <NfrFindingsDrawer open={findingsOpen} findings={findings} validating={validating}
                         onClose={() => setFindingsOpen(false)} onValidate={handleValidate} />
    </div>
  )
}

function Header({ onBack, status, onValidate, onExport, showActions }: {
  onBack: () => void
  status: string | null
  onValidate: () => void
  onExport: () => void
  showActions: boolean
}) {
  return (
    <div className="flex items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-4 py-2.5">
      <button onClick={onBack} className="text-[var(--text-tertiary)] hover:text-[var(--text-primary)]"><ChevronLeft size={16} /></button>
      <h1 className="text-sm font-semibold text-[var(--text-primary)]">NFR Builder</h1>
      {status === 'validated' && <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-700">Validated ✓</span>}
      {status === 'generating' && <span className="rounded bg-blue-100 px-1.5 py-0.5 text-[9px] font-semibold text-blue-700 animate-pulse">Generating…</span>}
      {showActions && (
        <div className="ml-auto flex items-center gap-1.5">
          <button onClick={onExport} className="inline-flex items-center gap-1 rounded-md border border-[var(--border-default)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]">
            <Download size={12} /> Export
          </button>
          <button onClick={onValidate} className="inline-flex items-center gap-1 rounded-md bg-[var(--accent)] px-2.5 py-1 text-xs font-medium text-white">
            <ShieldCheck size={12} /> Validate
          </button>
        </div>
      )}
    </div>
  )
}
