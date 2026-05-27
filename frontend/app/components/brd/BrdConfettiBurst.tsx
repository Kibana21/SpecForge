'use client'
import { useEffect, useState } from 'react'

export function BrdConfettiBurst({ active }: { active: boolean }) {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    if (active) {
      setVisible(true)
      const t = setTimeout(() => setVisible(false), 700)
      return () => clearTimeout(t)
    }
  }, [active])

  if (!visible) return null

  const particles = [
    { color: '#2F6B4C', x: 45, delay: 0 },
    { color: '#10B981', x: 47, delay: 60 },
    { color: '#6366F1', x: 49, delay: 120 },
    { color: '#F59E0B', x: 51, delay: 180 },
    { color: '#EF4444', x: 53, delay: 240 },
    { color: '#8B5CF6', x: 55, delay: 300 },
  ]

  return (
    <div className="fixed inset-0 pointer-events-none z-50" aria-hidden>
      {particles.map((p, i) => (
        <div
          key={i}
          className="absolute w-2 h-2 rounded-full animate-confetti"
          style={{
            backgroundColor: p.color,
            left: `${p.x}%`,
            top: '30%',
            animationDelay: `${p.delay}ms`,
          }}
        />
      ))}
    </div>
  )
}
