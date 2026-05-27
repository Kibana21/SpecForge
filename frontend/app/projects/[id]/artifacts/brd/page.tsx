'use client'
import { useParams, useRouter } from 'next/navigation'
import { BrdBuilderView } from '@/app/components/brd/BrdBuilderView'

export default function BrdPage() {
  const params = useParams()
  const router = useRouter()
  const projectId = params.id as string

  return (
    <div className="h-screen overflow-hidden">
      <BrdBuilderView
        projectId={projectId}
        onBack={() => router.push(`/projects/${projectId}`)}
      />
    </div>
  )
}
