'use client'

import { createContext, useContext, useState, useCallback, ReactNode } from 'react'

interface ProjectContext {
  activeProjectId: string | null
  activeDocumentKey: string | null
  activeStage: string | null
  versionPanelOpen: boolean
  setActiveProject: (id: string | null) => void
  setActiveDocumentKey: (key: string | null) => void
  setActiveStage: (stage: string | null) => void
  openVersionPanel: (documentKey: string) => void
  closeVersionPanel: () => void
}

const Ctx = createContext<ProjectContext | null>(null)

export function ProjectContextProvider({ children }: { children: ReactNode }) {
  const [activeProjectId, setActiveProjectId] = useState<string | null>(null)
  const [activeDocumentKey, setActiveDocumentKey] = useState<string | null>(null)
  const [activeStage, setActiveStage] = useState<string | null>(null)
  const [versionPanelOpen, setVersionPanelOpen] = useState(false)

  const setActiveProject = useCallback((id: string | null) => {
    setActiveProjectId(id)
  }, [])

  const setActiveDocKey = useCallback((key: string | null) => {
    setActiveDocumentKey(key)
  }, [])

  const setStage = useCallback((stage: string | null) => {
    setActiveStage(stage)
  }, [])

  const openVersionPanel = useCallback((documentKey: string) => {
    setActiveDocumentKey(documentKey)
    setVersionPanelOpen(true)
  }, [])

  const closeVersionPanel = useCallback(() => {
    setVersionPanelOpen(false)
  }, [])

  return (
    <Ctx.Provider
      value={{
        activeProjectId,
        activeDocumentKey,
        activeStage,
        versionPanelOpen,
        setActiveProject,
        setActiveDocumentKey: setActiveDocKey,
        setActiveStage: setStage,
        openVersionPanel,
        closeVersionPanel,
      }}
    >
      {children}
    </Ctx.Provider>
  )
}

export function useProjectContext(): ProjectContext {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useProjectContext must be used inside ProjectContextProvider')
  return ctx
}
