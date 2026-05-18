import { useCallback, useRef, useState } from 'react'

export type SaveFn = (content: string) => Promise<void>

export function useDebouncedSave(saveFn: SaveFn, delay = 500) {
  const [status, setStatus] = useState<'idle' | 'saving' | 'saved'>('idle')
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const save = useCallback(
    (content: string) => {
      setStatus('saving')
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(async () => {
        try {
          await saveFn(content)
          setStatus('saved')
        } catch {
          setStatus('idle')
        }
      }, delay)
    },
    [saveFn, delay]
  )

  return { save, status }
}
