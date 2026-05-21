import Link from 'next/link'
import { Layers, ArrowLeft } from 'lucide-react'

export default function NotFound() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
      <div className="text-center max-w-md px-6">
        <div className="flex justify-center mb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-[var(--bg-surface)] border border-[var(--border-default)] shadow-sm">
            <Layers size={28} className="text-[var(--text-tertiary)]" strokeWidth={1.4} />
          </div>
        </div>
        <h1 className="text-5xl font-bold text-[var(--text-primary)] mb-2">404</h1>
        <p className="text-lg font-semibold text-[var(--text-primary)] mb-2">Page not found</p>
        <p className="text-sm text-[var(--text-secondary)] mb-8">
          The page you are looking for does not exist or has been moved.
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 rounded-lg bg-[var(--accent)] hover:bg-[var(--accent-hover)] px-5 py-2.5 text-sm font-semibold text-white transition-colors"
        >
          <ArrowLeft size={15} />
          Back to dashboard
        </Link>
      </div>
    </main>
  )
}
