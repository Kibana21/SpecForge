'use client'
import { useState, useEffect } from 'react'
import { Sparkles } from 'lucide-react'
import { api } from '@/lib/api'
import { motion } from 'framer-motion'

interface Props {
  projectId: string
  onSelect: (question: string) => void
}

const GENERIC_STARTERS = [
  'What does this project need to deliver?',
  'What are the main risks and constraints?',
  'Who are the key stakeholders and roles?',
  'Summarise the project objective.',
]

export function StarterChips({ projectId, onSelect }: Props) {
  const [starters, setStarters] = useState<string[]>([])

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [wiki, understanding] = await Promise.allSettled([
          api.projects.getWiki(projectId),
          api.projects.understanding(projectId),
        ])
        if (cancelled) return
        const questions: string[] = []
        if (wiki.status === 'fulfilled') {
          const top = (wiki.value?.concepts ?? []).slice(0, 2)
          for (const c of top) {
            questions.push(`How does "${c.title}" work in this project?`)
          }
          if (top.length > 0) {
            questions.push(`What are the risks around "${top[0].title}"?`)
          }
        }
        const obj = understanding.status === 'fulfilled'
          ? understanding.value?.understanding?.objective
          : null
        if (obj) questions.push(`Summarize: ${obj.slice(0, 80)}`)
        if (!cancelled) {
          setStarters(questions.length >= 2 ? questions.slice(0, 4) : GENERIC_STARTERS)
        }
      } catch {
        if (!cancelled) setStarters(GENERIC_STARTERS)
      }
    }
    load()
    return () => { cancelled = true }
  }, [projectId])

  const chips = starters.length > 0 ? starters : GENERIC_STARTERS

  return (
    <div className="flex flex-col items-center gap-4 py-8 text-center">
      <div className="w-12 h-12 rounded-full bg-[var(--bg-elevated)] border border-[var(--border-default)] flex items-center justify-center">
        <Sparkles size={20} className="text-[var(--accent)]" strokeWidth={1.5} />
      </div>
      <div>
        <p className="text-sm font-medium text-[var(--text-primary)]">Ask the Project</p>
        <p className="text-xs text-[var(--text-tertiary)] mt-0.5 max-w-[320px]">
          Navigate source documents, wiki concepts, and app facts. Answers are cited and traceable.
        </p>
      </div>
      <div className="flex flex-wrap gap-2 justify-center max-w-[520px]">
        {chips.map((q, i) => (
          <motion.button
            key={i}
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06 }}
            onClick={() => onSelect(q)}
            className="text-xs px-3 py-1.5 rounded-full border border-[var(--border-default)] bg-[var(--bg-elevated)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-colors text-left"
          >
            {q}
          </motion.button>
        ))}
      </div>
    </div>
  )
}
