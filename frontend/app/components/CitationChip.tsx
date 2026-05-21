import type { CitationItem } from '@/lib/types'

interface Props {
  citation: CitationItem
  index: number
}

export function CitationChip({ citation, index }: Props) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-[var(--accent-blue-subtle)] border border-[var(--accent-blue)] px-2 py-0.5 text-[10px] font-medium text-[var(--accent-blue)] cursor-default"
      title={citation.text_excerpt}
    >
      <span>[{index + 1}]</span>
      <span className="text-[var(--text-tertiary)] max-w-[120px] truncate">{citation.doc_name}</span>
    </span>
  )
}
