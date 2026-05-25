'use client'
import { useParams, useRouter } from 'next/navigation'
import { ArtifactBuilderPanel } from '@/app/components/ArtifactBuilderPanel'

export default function ArtifactBuilderPage() {
  const { id: projectId, type: artifactType } = useParams() as { id: string; type: string }
  const router = useRouter()
  return (
    <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-base)]">
      <ArtifactBuilderPanel
        projectId={projectId}
        artifactType={artifactType}
        onBack={() => router.push(`/projects/${projectId}`)}
      />
    </div>
  )
}
