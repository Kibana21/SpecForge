'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from 'react'
import { tokenStore } from './tokenStore'

export type User = {
  id: string
  email: string
  display_name: string
  role: string
  status: string
  is_test: boolean
}

type AuthState = {
  user: User | null
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthState | null>(null)

async function fetchMe(token: string): Promise<User | null> {
  const res = await fetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${token}` },
    credentials: 'include',
  })
  if (!res.ok) return null
  const json = await res.json()
  return (json.data as User) ?? null
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount: attempt to restore session via refresh cookie
  useEffect(() => {
    ;(async () => {
      try {
        const res = await fetch('/api/auth/refresh', {
          method: 'POST',
          credentials: 'include',
        })
        if (res.ok) {
          const json = await res.json()
          const token: string = json.data?.access_token
          if (token) {
            tokenStore.set(token)
            const me = await fetchMe(token)
            setUser(me)
          }
        }
      } catch {
        // no valid session
      } finally {
        setIsLoading(false)
      }
    })()
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    })
    const json = await res.json()
    if (!res.ok) {
      // Surface the backend error message; fall back to generic
      const msg =
        json?.error?.message ??
        json?.detail?.[0]?.msg ??
        json?.detail ??
        'Login failed'
      throw new Error(String(msg))
    }
    const token: string = json.data?.access_token
    tokenStore.set(token)
    const me = await fetchMe(token)
    setUser(me)
  }, [])

  const logout = useCallback(async () => {
    const token = tokenStore.get()
    try {
      await fetch('/api/auth/logout', {
        method: 'POST',
        credentials: 'include',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      })
    } catch {
      // ignore network errors on logout
    }
    tokenStore.set(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be inside AuthProvider')
  return ctx
}
