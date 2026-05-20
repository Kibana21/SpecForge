'use client'

import { FormEvent, useState } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import { Layers, Eye, EyeOff, LogIn } from 'lucide-react'
import { useAuth } from '@/lib/auth/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const router = useRouter()
  const searchParams = useSearchParams()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setIsLoading(true)
    try {
      await login(email.trim(), password)
      const redirect = searchParams.get('redirect') ?? '/'
      router.replace(redirect)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-[var(--bg-base)]">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2.5 mb-8 justify-center">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-[var(--accent-blue)] shadow-sm">
            <Layers size={18} className="text-white" />
          </div>
          <span className="text-xl font-bold text-[var(--text-primary)] tracking-tight">
            SpecForge AI
          </span>
        </div>

        {/* Card */}
        <div className="rounded-2xl border border-[var(--border-default)] bg-[var(--bg-surface)] p-8 shadow-sm">
          <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
            Sign in
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mb-6">
            Enter your credentials to continue
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Email */}
            <div>
              <label
                htmlFor="email"
                className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5 uppercase tracking-wide"
              >
                Email
              </label>
              <input
                id="email"
                type="text"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3.5 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-tertiary)] outline-none transition focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20"
              />
            </div>

            {/* Password */}
            <div>
              <label
                htmlFor="password"
                className="block text-xs font-semibold text-[var(--text-secondary)] mb-1.5 uppercase tracking-wide"
              >
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full rounded-lg border border-[var(--border-default)] bg-[var(--bg-base)] px-3.5 py-2.5 pr-10 text-sm text-[var(--text-primary)] placeholder-[var(--text-tertiary)] outline-none transition focus:border-[var(--accent-blue)] focus:ring-2 focus:ring-[var(--accent-blue)]/20"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-tertiary)] hover:text-[var(--text-secondary)] transition-colors"
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Submit */}
            <button
              type="submit"
              disabled={isLoading}
              className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--accent-blue)] hover:bg-[var(--accent-blue-hover)] disabled:opacity-60 px-4 py-2.5 text-sm font-semibold text-white transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)] focus:ring-offset-2"
            >
              {isLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              ) : (
                <LogIn size={15} />
              )}
              {isLoading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>

        {/* Test accounts hint */}
        <details className="mt-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] text-xs">
          <summary className="cursor-pointer px-4 py-3 font-medium text-[var(--text-tertiary)] select-none">
            Test accounts
          </summary>
          <div className="border-t border-[var(--border-subtle)] px-4 pb-3 pt-2 space-y-1 font-mono">
            {[
              ['admin@specforge.test', 'platform_admin'],
              ['analyst@specforge.test', 'business_analyst'],
              ['owner@specforge.test', 'product_owner'],
              ['architect@specforge.test', 'solution_architect'],
              ['appowner@specforge.test', 'app_owner'],
              ['qa@specforge.test', 'qa_lead'],
              ['reviewer@specforge.test', 'compliance_reviewer'],
            ].map(([email, role]) => (
              <button
                key={email}
                type="button"
                onClick={() => {
                  setEmail(email)
                  setPassword('SpecForge#Test2026!')
                }}
                className="flex w-full items-center justify-between gap-2 rounded px-1 py-0.5 text-left hover:bg-[var(--bg-elevated)] transition-colors"
              >
                <span className="text-[var(--text-secondary)]">{email}</span>
                <span className="text-[var(--text-tertiary)] shrink-0">{role}</span>
              </button>
            ))}
            <p className="pt-1 text-[var(--text-tertiary)]">
              Password: <span className="text-[var(--text-secondary)]">SpecForge#Test2026!</span>
            </p>
          </div>
        </details>
      </div>
    </div>
  )
}
