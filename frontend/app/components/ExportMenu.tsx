'use client'
import { Download, ChevronDown } from 'lucide-react'
import type { SpecType } from '@/lib/types'
import { api } from '@/lib/api'
import { Button } from '@/app/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/app/components/ui/dropdown-menu'

const EXPORT_OPTIONS: { key: SpecType | 'all'; label: string }[] = [
  { key: 'functional', label: 'Functional Spec' },
  { key: 'technical', label: 'Technical Spec' },
  { key: 'user_stories', label: 'User Stories' },
  { key: 'review', label: 'Review' },
  { key: 'all', label: 'All (combined)' },
]

export function ExportMenu({ projectId }: { projectId: string }) {
  function download(specType: string) {
    window.location.href = api.specs.exportUrl(projectId, specType)
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <Download size={13} />
          Export
          <ChevronDown size={11} />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-44">
        {EXPORT_OPTIONS.map(({ key, label }) => (
          <DropdownMenuItem key={key} onClick={() => download(key)} className="cursor-pointer">
            <Download size={11} />
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
