'use client'
import { useEffect } from 'react'
import { useEditor, EditorContent } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'
import Placeholder from '@tiptap/extension-placeholder'
import type { SpecVersion } from '@/lib/types'
import { api } from '@/lib/api'
import { useDebouncedSave } from '@/lib/hooks/useDebouncedSave'
import { SavingIndicator } from './SavingIndicator'

function toDoc(markdown: string) {
  const paras = (markdown || '').split(/\n\n+/).map((p) => p.trim()).filter(Boolean)
  if (paras.length === 0) return { type: 'doc', content: [{ type: 'paragraph' }] }
  return {
    type: 'doc',
    content: paras.map((p) => ({ type: 'paragraph', content: [{ type: 'text', text: p }] })),
  }
}

interface SpecEditorProps {
  projectId: string
  spec: SpecVersion
  onSaved?: () => void
}

export function SpecEditor({ projectId, spec, onSaved }: SpecEditorProps) {
  const saveFn = async (content: string) => {
    await api.specs.patch(projectId, spec.id, { content_markdown: content })
    onSaved?.()
  }

  const { save, status } = useDebouncedSave(saveFn, 500)

  const editor = useEditor({
    extensions: [
      StarterKit,
      Placeholder.configure({ placeholder: 'Start editing the spec…' }),
    ],
    content: toDoc(spec.content_markdown ?? ''),
    editorProps: {
      attributes: {
        class: 'prose prose-sm max-w-none focus:outline-none px-6 py-5 min-h-[400px] text-[var(--text-primary)]',
      },
    },
    onUpdate({ editor: e }) {
      const text = e.getJSON().content
        ?.map((node) => node.content?.map((n) => ('text' in n ? n.text ?? '' : '')).join('') ?? '')
        .join('\n\n') ?? ''
      save(text)
    },
  })

  useEffect(() => {
    if (editor && !editor.isDestroyed) {
      editor.commands.setContent(toDoc(spec.content_markdown ?? ''))
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec.id])

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-6 py-2.5 border-b border-[var(--border-subtle)] bg-[var(--bg-elevated)]">
        <p className="text-[11px] text-[var(--text-tertiary)]">
          Editing · markdown preserved as-is
        </p>
        <SavingIndicator status={status} />
      </div>
      <div className="flex-1 overflow-y-auto bg-[var(--bg-surface)]">
        <EditorContent editor={editor} />
      </div>
    </div>
  )
}
