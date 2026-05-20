'use client'

import { useState, useRef, useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { LogOut, ChevronDown, TestTube2 } from 'lucide-react'
import { useAuth } from '@/lib/auth/AuthContext'

export function UserMenu() {
  const { user, logout } = useAuth()
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  if (!user) return null

  const initials = user.display_name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  async function handleLogout() {
    setOpen(false)
    await logout()
    router.push('/login')
  }

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-sm transition hover:bg-[var(--bg-elevated)] focus:outline-none focus:ring-2 focus:ring-[var(--accent-blue)] focus:ring-offset-1"
      >
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--accent-blue)] text-xs font-bold text-white">
          {initials}
        </span>
        <span className="text-[var(--text-secondary)] max-w-[120px] truncate hidden sm:block">
          {user.display_name}
        </span>
        {user.is_test && (
          <TestTube2 size={12} className="text-amber-500 shrink-0" />
        )}
        <ChevronDown size={13} className="text-[var(--text-tertiary)]" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-56 rounded-xl border border-[var(--border-default)] bg-[var(--bg-surface)] shadow-md z-50 py-1">
          <div className="px-3 py-2 border-b border-[var(--border-subtle)]">
            <p className="text-sm font-semibold text-[var(--text-primary)] truncate">
              {user.display_name}
            </p>
            <p className="text-xs text-[var(--text-tertiary)] truncate">{user.email}</p>
            <span className="mt-1 inline-block rounded-full bg-[var(--bg-elevated)] px-2 py-0.5 text-xs font-medium text-[var(--text-secondary)]">
              {user.role.replace(/_/g, ' ')}
            </span>
          </div>
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] transition-colors"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      )}
    </div>
  )
}
