'use client'

import { motion, useReducedMotion } from 'framer-motion'

export default function Template({ children }: { children: React.ReactNode }) {
  const reduce = useReducedMotion()
  if (reduce) return <>{children}</>
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
      className="h-full"
    >
      {children}
    </motion.div>
  )
}
