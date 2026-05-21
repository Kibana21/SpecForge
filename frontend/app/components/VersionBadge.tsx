import { Badge } from '@/app/components/ui/badge'

export function VersionBadge({ version }: { version: number }) {
  if (version <= 1) return null
  return <Badge variant="info">v{version}</Badge>
}
