'use client'

import { motion, useReducedMotion, type Variants, type HTMLMotionProps } from 'framer-motion'
import { type ReactNode } from 'react'

// ── Shared easing / variants ────────────────────────────────────────────────
const EASE = [0.22, 1, 0.36, 1] as const // gentle "easeOutExpo"-ish

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 10 },
  show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE } },
}

export const staggerContainer: Variants = {
  hidden: {},
  show: { transition: { staggerChildren: 0.05, delayChildren: 0.04 } },
}

// ── FadeIn: a single element that fades/slides in on mount ───────────────────
export function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode
  delay?: number
  className?: string
}) {
  const reduce = useReducedMotion()
  if (reduce) return <div className={className}>{children}</div>
  return (
    <motion.div
      className={className}
      initial="hidden"
      animate="show"
      variants={{
        hidden: { opacity: 0, y: 10 },
        show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: EASE, delay } },
      }}
    >
      {children}
    </motion.div>
  )
}

// ── Stagger: container that staggers its <StaggerItem> children on mount ─────
export function Stagger({
  children,
  className,
}: {
  children: ReactNode
  className?: string
}) {
  const reduce = useReducedMotion()
  if (reduce) return <div className={className}>{children}</div>
  return (
    <motion.div className={className} initial="hidden" animate="show" variants={staggerContainer}>
      {children}
    </motion.div>
  )
}

export function StaggerItem({
  children,
  className,
  ...props
}: { children: ReactNode; className?: string } & HTMLMotionProps<'div'>) {
  const reduce = useReducedMotion()
  if (reduce) return <div className={className}>{children}</div>
  return (
    <motion.div className={className} variants={fadeInUp} {...props}>
      {children}
    </motion.div>
  )
}

export { motion, useReducedMotion }
