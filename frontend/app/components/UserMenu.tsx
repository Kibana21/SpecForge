'use client'

import { useRouter } from 'next/navigation'
import { LogOut, ChevronDown, TestTube2 } from 'lucide-react'
import { useAuth } from '@/lib/auth/AuthContext'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/app/components/ui/dropdown-menu'

export function UserMenu() {
  const { user, logout } = useAuth()
  const router = useRouter()

  if (!user) return null

  const initials = user.display_name
    .split(' ')
    .map((w) => w[0])
    .join('')
    .toUpperCase()
    .slice(0, 2)

  async function handleLogout() {
    await logout()
    router.push('/login')
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-lg border border-[var(--border-default)] bg-[var(--bg-surface)] px-3 py-1.5 text-sm transition hover:bg-[var(--bg-elevated)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-ring)] focus-visible:ring-offset-1">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--accent)] text-xs font-bold text-white">
          {initials}
        </span>
        <span className="text-[var(--text-secondary)] max-w-[120px] truncate hidden sm:block">
          {user.display_name}
        </span>
        {user.is_test && <TestTube2 size={12} className="text-warning shrink-0" />}
        <ChevronDown size={13} className="text-[var(--text-tertiary)]" />
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="font-normal">
          <p className="text-sm font-semibold text-[var(--text-primary)] truncate">{user.display_name}</p>
          <p className="text-xs text-[var(--text-tertiary)] truncate">{user.email}</p>
          <span className="mt-1.5 inline-block rounded-full bg-[var(--bg-elevated)] px-2 py-0.5 text-[10px] font-medium capitalize text-[var(--text-secondary)]">
            {user.role.replace(/_/g, ' ')}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onClick={handleLogout} className="cursor-pointer">
          <LogOut size={14} />
          Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
