'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Layers,
  LayoutDashboard,
  BookOpen,
  Brain,
  ShieldCheck,
  ChevronRight,
  CheckCircle2,
  Circle,
  Menu,
  X,
} from 'lucide-react'
import { useAuth } from '@/lib/auth/AuthContext'
import { cn } from '@/lib/utils'

// Seeded 10-stage SDLC progress for E0
const SDLC_STAGES = [
  { key: 'business-context',    label: 'Business Context',      done: false },
  { key: 'user-requirements',   label: 'User Requirements',     done: false },
  { key: 'functional-specs',    label: 'Functional Specs',      done: false },
  { key: 'technical-arch',      label: 'Technical Architecture', done: false },
  { key: 'data-model',          label: 'Data Model',            done: false },
  { key: 'api-design',          label: 'API Design',            done: false },
  { key: 'security-review',     label: 'Security Review',       done: false },
  { key: 'test-planning',       label: 'Test Planning',         done: false },
  { key: 'deployment-plan',     label: 'Deployment Plan',       done: false },
  { key: 'operations-guide',    label: 'Operations Guide',      done: false },
] as const

const NAV_ITEMS = [
  { href: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { href: '/apps', icon: Brain, label: 'App Registry' },
  { href: '/audit', icon: ShieldCheck, label: 'Audit Log', roles: ['platform_admin', 'compliance_reviewer'] },
] as const

interface Props {
  children: React.ReactNode
}

export function AppShell({ children }: Props) {
  const pathname = usePathname()
  const { user } = useAuth()
  const [mobileOpen, setMobileOpen] = useState(false)

  // Close the mobile drawer whenever the route changes.
  useEffect(() => { setMobileOpen(false) }, [pathname])

  const visibleNav = NAV_ITEMS.filter(
    (item) => !('roles' in item) || (user && item.roles.includes(user.role as never))
  )

  return (
    <div className="flex h-screen overflow-hidden">
      {/* Mobile top bar */}
      <div className="md:hidden fixed inset-x-0 top-0 z-30 flex h-12 items-center gap-3 border-b border-[var(--border-default)] bg-[var(--bg-surface)] px-3">
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation"
          className="rounded-lg p-1.5 text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)]"
        >
          <Menu size={18} />
        </button>
        <div className="flex items-center gap-2">
          <div className="flex h-6 w-6 items-center justify-center rounded-md bg-[var(--accent)]">
            <Layers size={12} className="text-white" />
          </div>
          <span className="text-sm font-bold tracking-tight text-[var(--text-primary)]">SpecForge AI</span>
        </div>
      </div>

      {/* Mobile backdrop */}
      <AnimatePresence>
        {mobileOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            onClick={() => setMobileOpen(false)}
            className="md:hidden fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
          />
        )}
      </AnimatePresence>

      {/* Sidebar — static on md+, slide-in drawer on mobile */}
      <aside
        className={cn(
          'z-50 flex w-56 shrink-0 flex-col overflow-y-auto border-r border-[var(--border-default)] bg-[var(--bg-sidebar)]',
          'transition-transform duration-200 ease-out',
          'max-md:fixed max-md:inset-y-0 max-md:left-0',
          'md:static md:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        )}
      >
        {/* Brand */}
        <div className="flex items-center justify-between gap-2.5 px-4 py-4 border-b border-[var(--border-subtle)]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--accent)] shrink-0">
              <Layers size={14} className="text-white" />
            </div>
            <span className="text-sm font-bold text-[var(--text-primary)] tracking-tight">
              SpecForge AI
            </span>
          </div>
          {/* Close (mobile only) */}
          <button
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
            className="md:hidden rounded-lg p-1 text-[var(--text-tertiary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]"
          >
            <X size={16} />
          </button>
        </div>

        {/* Primary nav */}
        <nav className="px-2 py-3 space-y-0.5">
          {visibleNav.map(({ href, icon: Icon, label }) => {
            const active = pathname === href
            return (
              <Link
                key={href}
                href={href}
                className={`relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${
                  active
                    ? 'bg-[var(--accent-subtle)] text-[var(--accent-deep)] font-semibold'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)]'
                }`}
              >
                {active && (
                  <motion.span
                    layoutId="sidebar-active"
                    transition={{ type: 'spring', stiffness: 500, damping: 35 }}
                    className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-[var(--accent)]"
                  />
                )}
                <Icon size={14} strokeWidth={active ? 2.5 : 2} className={active ? 'text-[var(--accent)]' : ''} />
                {label}
              </Link>
            )
          })}
        </nav>

        {/* SDLC stage progress */}
        <div className="px-2 pt-2 pb-3 border-t border-[var(--border-subtle)] mt-1">
          <p className="px-2 pb-2 text-[9px] font-semibold uppercase tracking-widest text-[var(--text-tertiary)]">
            SDLC Progress
          </p>
          <div className="space-y-0.5">
            {SDLC_STAGES.map((stage, idx) => (
              <div
                key={stage.key}
                className="flex items-center gap-2 px-2 py-1.5 rounded-md"
              >
                {stage.done ? (
                  <CheckCircle2 size={11} className="shrink-0 text-success" />
                ) : (
                  <Circle size={11} className="shrink-0 text-[var(--border-default)]" />
                )}
                <span className="text-[11px] text-[var(--text-tertiary)] leading-none truncate">
                  {idx + 1}. {stage.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Org library link */}
        <div className="px-2 py-2 border-t border-[var(--border-subtle)]">
          <Link
            href="/"
            className="flex items-center justify-between gap-2 rounded-lg px-2.5 py-2 text-sm text-[var(--text-secondary)] hover:bg-[var(--bg-elevated)] hover:text-[var(--text-primary)] transition-colors"
          >
            <div className="flex items-center gap-2">
              <BookOpen size={13} />
              <span className="text-[11px]">Org Library</span>
            </div>
            <ChevronRight size={11} className="text-[var(--text-tertiary)]" />
          </Link>
        </div>

        {/* User identity at bottom */}
        {user && (
          <div className="mt-auto px-3 py-3 border-t border-[var(--border-subtle)]">
            <div className="flex items-center gap-2.5">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--accent)] shrink-0">
                <span className="text-[10px] font-bold text-white">
                  {user.display_name.split(' ').map((w) => w[0]).join('').toUpperCase().slice(0, 2)}
                </span>
              </div>
              <div className="min-w-0">
                <p className="text-xs font-semibold text-[var(--text-primary)] truncate leading-none">
                  {user.display_name}
                </p>
                <p className="text-[10px] text-[var(--text-tertiary)] truncate mt-0.5">
                  {user.role.replace(/_/g, ' ')}
                </p>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* Main area (offset below the mobile top bar) */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden max-md:pt-12">
        {children}
      </div>
    </div>
  )
}
