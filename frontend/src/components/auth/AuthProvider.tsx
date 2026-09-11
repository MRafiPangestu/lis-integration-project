import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react"
import { login as loginRequest } from "../../api/endpoints"
import { setAuthToken, setUnauthorizedHandler } from "../../api/client"
import type { UserPublic } from "../../types/api"

// M9.1a design §12.2: sessionStorage — survives reload, clears on tab close,
// per-tab. Never the password itself, only the issued token + display info.
const STORAGE_KEY = "lis.auth"

interface StoredSession {
  token: string
  user: UserPublic
}

function readStoredSession(): StoredSession | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredSession
    if (!parsed?.token || !parsed?.user) return null
    return parsed
  } catch {
    return null
  }
}

function writeStoredSession(session: StoredSession | null): void {
  try {
    if (session) {
      window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(session))
    } else {
      window.sessionStorage.removeItem(STORAGE_KEY)
    }
  } catch {
    // sessionStorage unavailable (private mode, disabled site data, ...) —
    // the session simply will not survive a reload. Not fatal.
  }
}

interface AuthContextValue {
  user: UserPublic | null
  isAuthenticated: boolean
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(() => {
    // Prime the fetch chokepoint during state initialisation, not in an
    // effect. Effects run child-first, so a restored session would otherwise
    // only reach client.ts after descendants had already set up their own
    // fetches — leaving the very first request on a reload unauthenticated,
    // and a 401 would then destroy the session we had just restored.
    const restored = readStoredSession()
    setAuthToken(restored?.token ?? null)
    return restored
  })

  // Keep the chokepoint in sync for every *later* change (login, logout, an
  // expiry-driven 401). The initial value is already applied above; assigning
  // the same token again is a no-op.
  useEffect(() => {
    setAuthToken(session?.token ?? null)
  }, [session])

  const logout = useCallback(() => {
    setSession(null)
    writeStoredSession(null)
  }, [])

  // A 401 from any request (expired token, disabled account, ...) logs out
  // through the same path client.ts already uses — no proactive expiry
  // timer (design §12.2 point 5).
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const login = useCallback(async (username: string, password: string) => {
    const response = await loginRequest(username, password)
    const next: StoredSession = { token: response.access_token, user: response.user }
    setSession(next)
    writeStoredSession(next)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user: session?.user ?? null,
      isAuthenticated: session !== null,
      login,
      logout,
    }),
    [session, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider")
  }
  return context
}
