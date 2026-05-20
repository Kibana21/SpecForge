'use client'
import { VersionHistoryPanel } from '@/app/components/VersionHistoryPanel'

export default function ProjectLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      {children}
      <VersionHistoryPanel />
    </>
  )
}
