import type { TcTestType, TcPriority, TcTraceKind } from '@/lib/types'

export const TC_TYPE_STYLES: Record<TcTestType, { label: string; bg: string; text: string; border: string; emoji: string }> = {
  functional:  { label: 'Functional',  bg: 'bg-emerald-50', text: 'text-emerald-700', border: 'border-emerald-200', emoji: '✓' },
  integration: { label: 'Integration', bg: 'bg-blue-50',    text: 'text-blue-700',    border: 'border-blue-200',    emoji: '🔗' },
  e2e:         { label: 'E2E',          bg: 'bg-violet-50',  text: 'text-violet-700',  border: 'border-violet-200',  emoji: '🛣' },
  negative:    { label: 'Negative',     bg: 'bg-red-50',     text: 'text-red-700',     border: 'border-red-200',     emoji: '✗' },
  edge_case:   { label: 'Edge case',    bg: 'bg-amber-50',   text: 'text-amber-700',   border: 'border-amber-200',   emoji: '⚡' },
  responsive:  { label: 'Responsive',   bg: 'bg-sky-50',     text: 'text-sky-700',     border: 'border-sky-200',     emoji: '📱' },
}

export const TC_PRIORITY_STYLES: Record<TcPriority, { bg: string; text: string; border: string }> = {
  P0: { bg: 'bg-red-50',   text: 'text-red-700',   border: 'border-red-200' },
  P1: { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' },
  P2: { bg: 'bg-blue-50',  text: 'text-blue-700',  border: 'border-blue-200' },
  P3: { bg: 'bg-gray-50',  text: 'text-gray-500',  border: 'border-gray-200' },
}

export const TC_TRACE_STYLES: Record<TcTraceKind, { label: string; bg: string; text: string }> = {
  frs_acceptance_scenario:    { label: 'AS',  bg: 'bg-pink-50',    text: 'text-pink-700' },
  frs_functional_requirement: { label: 'FR',  bg: 'bg-indigo-50',  text: 'text-indigo-700' },
  frs_business_rule:          { label: 'BR',  bg: 'bg-amber-50',   text: 'text-amber-700' },
  frs_screen:                 { label: 'SCR', bg: 'bg-sky-50',     text: 'text-sky-700' },
  frs_spec:                   { label: 'Spec', bg: 'bg-slate-50',  text: 'text-slate-700' },
  brd_business_requirement:   { label: 'BRD', bg: 'bg-emerald-50', text: 'text-emerald-700' },
  within_test_cases:          { label: 'TC',  bg: 'bg-gray-50',    text: 'text-gray-600' },
}

export const TC_TEST_TYPES: TcTestType[] = ['functional', 'integration', 'e2e', 'negative', 'edge_case', 'responsive']
export const TC_PRIORITIES: TcPriority[] = ['P0', 'P1', 'P2', 'P3']
export const TC_VIEWPORTS = ['mobile-360', 'tablet-768', 'desktop-1440']

export function coverageColor(pct: number): string {
  if (pct >= 100) return 'text-emerald-600'
  if (pct >= 80) return 'text-amber-600'
  return 'text-red-600'
}
