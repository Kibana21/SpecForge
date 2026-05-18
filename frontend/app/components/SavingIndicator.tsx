type SaveStatus = 'idle' | 'saving' | 'saved'

export function SavingIndicator({ status }: { status: SaveStatus }) {
  if (status === 'idle') return null
  return (
    <span className="text-xs text-[var(--text-tertiary)]">
      {status === 'saving' ? 'Saving…' : 'Saved'}
    </span>
  )
}
