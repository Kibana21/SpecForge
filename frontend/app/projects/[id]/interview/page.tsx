'use client'
import { useParams, useRouter } from 'next/navigation'
import { InterviewPanel } from '@/app/components/InterviewPanel'

export default function InterviewPage() {
  const { id: projectId } = useParams() as { id: string }
  const router = useRouter()
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-base)]">
      <InterviewPanel
        projectId={projectId}
        onValidated={() => router.push(`/projects/${projectId}`)}
      />
    </div>
  )
}
