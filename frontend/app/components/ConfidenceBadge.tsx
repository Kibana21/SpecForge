import type { Confidence } from '@/lib/types'
import { Badge } from '@/app/components/ui/badge'
import { confidenceVariant } from '@/lib/ui/status'

const label: Record<Confidence, string> = { high: 'High', medium: 'Med', low: 'Low' }

export function ConfidenceBadge({ confidence }: { confidence: Confidence }) {
  return <Badge variant={confidenceVariant[confidence]}>{label[confidence]}</Badge>
}
