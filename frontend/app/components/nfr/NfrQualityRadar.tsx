'use client'

import { useState } from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import type { NfrCategory, NfrRadarAxis } from '@/lib/types'
import { NFR_CATEGORIES, NFR_CATEGORY_LABEL } from '@/lib/nfr-manifest'

interface Props {
  radar: NfrRadarAxis[]
  activeCategory: NfrCategory | null
  onPick: (cat: NfrCategory) => void
  size?: number
}

const PRIORITY_COLORS: Record<string, string> = {
  must: 'var(--nfr-must)', should: 'var(--nfr-should)', could: 'var(--nfr-could)', wont: 'var(--nfr-wont)',
}

/** Signature 7-axis Quality Radar (vertical card). Polygon = MoSCoW-weighted mass;
 *  dashed ring = raw count; per-axis stacked spoke = priority composition.
 *  Hover an axis for its breakdown; click to filter the table. */
export function NfrQualityRadar({ radar, activeCategory, onPick, size = 240 }: Props) {
  const reduce = useReducedMotion()
  const [hover, setHover] = useState<NfrCategory | null>(null)
  const order = NFR_CATEGORIES.map((c) => c.key)
  const axes = order.map((k) => radar.find((a) => a.category === k) ?? {
    category: k, count: 0, weighted: 0, by_priority: { must: 0, should: 0, could: 0, wont: 0 },
  } as NfrRadarAxis)

  const cx = size / 2, cy = size / 2
  const R = size / 2 - 30
  const maxW = Math.max(1, ...axes.map((a) => a.weighted))
  const maxC = Math.max(1, ...axes.map((a) => a.count))
  const n = axes.length
  const angle = (i: number) => -Math.PI / 2 + (i * 2 * Math.PI) / n
  const pt = (i: number, r: number) => [cx + r * Math.cos(angle(i)), cy + r * Math.sin(angle(i))] as const

  const weightedPoly = axes.map((a, i) => pt(i, (a.weighted / maxW) * R).join(',')).join(' ')
  const countPoly = axes.map((a, i) => pt(i, (a.count / maxC) * R).join(',')).join(' ')
  const active = hover ?? activeCategory
  const totalNfrs = axes.reduce((s, a) => s + a.count, 0)

  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} className="shrink-0">
        {[0.25, 0.5, 0.75, 1].map((f) => (
          <polygon key={f} points={axes.map((_, i) => pt(i, R * f).join(',')).join(' ')}
                   fill="none" stroke="var(--nfr-radar-grid)" strokeWidth={1} />
        ))}
        {axes.map((a, i) => {
          const total = a.count || 1
          let acc = 0
          const segs: { p: string; r0: number; r1: number }[] = []
          for (const p of ['must', 'should', 'could', 'wont'] as const) {
            const c = a.by_priority?.[p] ?? 0
            if (!c) continue
            const r0 = (acc / total) * (a.count / maxC) * R
            acc += c
            const r1 = (acc / total) * (a.count / maxC) * R
            segs.push({ p, r0, r1 })
          }
          const dim = active && active !== a.category
          return (
            <g key={a.category}>
              <line x1={cx} y1={cy} x2={pt(i, R)[0]} y2={pt(i, R)[1]} stroke="var(--nfr-radar-axis)" strokeWidth={0.5} opacity={0.4} />
              {segs.map((s, j) => {
                const [x1, y1] = pt(i, s.r0); const [x2, y2] = pt(i, s.r1)
                return <line key={j} x1={x1} y1={y1} x2={x2} y2={y2} stroke={PRIORITY_COLORS[s.p]} strokeWidth={4} strokeLinecap="round" opacity={dim ? 0.25 : 1} />
              })}
            </g>
          )
        })}
        <polygon points={countPoly} fill="none" stroke="var(--nfr-radar-axis)" strokeWidth={1} strokeDasharray="3 3" opacity={0.55} />
        <motion.polygon
          points={weightedPoly}
          fill="var(--nfr-radar-fill)" stroke="var(--accent)" strokeWidth={1.5}
          initial={reduce ? false : { opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }}
          style={{ transformOrigin: `${cx}px ${cy}px` }} transition={{ duration: 0.5 }}
        />
        {axes.map((a, i) => {
          const cfg = NFR_CATEGORIES.find((c) => c.key === a.category)!
          const [lx, ly] = pt(i, R + 14)
          const [dx, dy] = pt(i, (a.weighted / maxW) * R)
          return (
            <g key={`lbl-${a.category}`} className="cursor-pointer"
               onMouseEnter={() => setHover(a.category)} onMouseLeave={() => setHover(null)}
               onClick={() => onPick(a.category)}>
              <circle cx={dx} cy={dy} r={active === a.category ? 4 : 3} fill="var(--accent)" />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="middle" fontSize={13} className="select-none">{cfg.emoji}</text>
            </g>
          )
        })}
        <text x={cx} y={cy - 3} textAnchor="middle" fontSize={18} fontWeight={700} fill="var(--text-primary)">{totalNfrs}</text>
        <text x={cx} y={cy + 12} textAnchor="middle" fontSize={9} fill="var(--text-tertiary)">NFRs</text>
      </svg>

      {/* detail / legend below the chart */}
      <div className="mt-1 w-full text-xs">
        {active ? (() => {
          const a = axes.find((x) => x.category === active)!
          return (
            <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-elevated)] p-2.5">
              <div className="font-semibold text-[var(--text-primary)]">{NFR_CATEGORY_LABEL[active]}</div>
              <div className="mb-1.5 text-[var(--text-tertiary)]">{a.count} NFRs · weight {a.weighted}</div>
              {(['must', 'should', 'could', 'wont'] as const).map((p) => (
                <div key={p} className="flex items-center gap-1.5 py-0.5">
                  <span className="inline-block h-2 w-2 rounded-sm" style={{ background: PRIORITY_COLORS[p] }} />
                  <span className="capitalize text-[var(--text-secondary)]">{p}</span>
                  <span className="ml-auto tabular-nums text-[var(--text-secondary)]">{a.by_priority?.[p] ?? 0}</span>
                </div>
              ))}
            </div>
          )
        })() : (
          <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 text-[10px] text-[var(--text-tertiary)]">
            {(['must', 'should', 'could', 'wont'] as const).map((p) => (
              <span key={p} className="inline-flex items-center gap-1">
                <span className="inline-block h-2 w-2 rounded-sm" style={{ background: PRIORITY_COLORS[p] }} /> {p}
              </span>
            ))}
            <span className="w-full text-center">Click an axis to filter ·  ┄ ring = count</span>
          </div>
        )}
      </div>
    </div>
  )
}
