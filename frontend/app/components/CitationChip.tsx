import type { CitationItem } from '@/lib/types'
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/app/components/ui/tooltip'

interface Props {
  citation: CitationItem
  index: number
}

export function CitationChip({ citation, index }: Props) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="inline-flex items-center gap-1 rounded-full bg-[var(--accent-subtle)] border border-[var(--accent)] px-2 py-0.5 text-[10px] font-medium text-[var(--accent-deep)] cursor-default">
          <span>[{index + 1}]</span>
          <span className="text-[var(--text-tertiary)] max-w-[120px] truncate">{citation.doc_name}</span>
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="text-xs font-semibold">{citation.doc_name}</p>
        <p className="mt-0.5 text-xs text-muted-foreground line-clamp-4">{citation.text_excerpt}</p>
      </TooltipContent>
    </Tooltip>
  )
}
