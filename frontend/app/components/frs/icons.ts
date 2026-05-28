/**
 * Lucide icon registry for FRS module capability icons.
 *
 * pickCapabilityIconName in lib/frs-manifest.ts returns a string;
 * this map turns the string into the actual component for rendering.
 */
import {
  Anchor, BarChart3, Bell, Box, CreditCard, Database, FileSearch, FileText,
  GitBranch, KeyRound, Layers, MessageSquare, Network, ScrollText, User,
  UserPlus, Workflow,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

import { pickCapabilityIconName } from '@/lib/frs-manifest'

const ICON_MAP: Record<string, LucideIcon> = {
  Anchor, BarChart3, Bell, Box, CreditCard, Database, FileSearch, FileText,
  GitBranch, KeyRound, Layers, MessageSquare, Network, ScrollText, User,
  UserPlus, Workflow,
}

/** Returns the LucideIcon component for a module slug. Always falls back to Box. */
export function pickCapabilityIcon(slug: string): LucideIcon {
  const name = pickCapabilityIconName(slug)
  return ICON_MAP[name] ?? Box
}
