import Link from 'next/link'
import { ShieldOff, ArrowLeft } from 'lucide-react'

export default function AccessDeniedPage() {
  return (
    <main className="min-h-screen flex items-center justify-center bg-[var(--bg-base)]">
      <div className="text-center max-w-md px-6">
        <div className="flex justify-center mb-6">
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-danger-bg border border-danger-border">
            <ShieldOff size={28} className="text-danger" strokeWidth={1.4} />
          </div>
        </div>
        <h1 className="text-2xl font-bold text-[var(--text-primary)] mb-2">Access denied</h1>
        <p className="text-sm text-[var(--text-secondary)] mb-8">
          You do not have permission to view this page. Contact your platform administrator
          if you believe this is an error.
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
