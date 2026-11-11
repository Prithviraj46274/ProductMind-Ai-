import React, { createContext, useContext, useState, useEffect } from 'react'
import { safeSet, safeRemove, STORAGE_KEYS } from '../services/storageService'
import { initialUser } from '../data/seedData'
import { authService } from '../services/api/authService'
import { isBackendConfigured } from '../services/api/apiClient'

const AuthContext = createContext(null)
const AUTH_TOKEN_KEY = 'pmai_mock_auth_session'

export function AuthProvider({ children }) {
  // Check active session and expiration on initialization
  const [currentUser, setCurrentUser] = useState(() => {
    const session = authService.getCurrentSession()
    return session?.user || null
  })

  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    const session = authService.getCurrentSession()
    return session !== null
  })

  const [isDemoAuth, setIsDemoAuth] = useState(() => {
    const session = authService.getCurrentSession()
    return session?.isDemo ?? !isBackendConfigured()
  })

  // Periodic session expiration check & refresh
  useEffect(() => {
    const interval = setInterval(async () => {
      const session = authService.getCurrentSession()
      if (!session && isAuthenticated) {
        setIsAuthenticated(false)
        setCurrentUser(null)
        safeRemove(AUTH_TOKEN_KEY)
      } else if (session && !session.isDemo) {
        // Refresh token if within 5 minutes of expiration
        const timeLeft = (session.expiresAt || 0) - Date.now()
        if (timeLeft > 0 && timeLeft < 5 * 60 * 1000) {
          const refreshed = await authService.refreshSession()
          if (refreshed?.user) {
            setCurrentUser(refreshed.user)
          }
        }
      }
    }, 60000)
    return () => clearInterval(interval)
  }, [isAuthenticated])

  /**
   * User Registration
   */
  const register = async ({ name, email, password }) => {
    const res = await authService.register({ name, email, password })
    if (res.success) {
      // Auto-login after successful registration
      return await login(email, password, true)
    }
    return { success: false, error: res.error || 'Registration failed.' }
  }

  /**
   * User Login
   */
  const login = async (email, password, rememberMe = true) => {
    const res = await authService.login(email, password, rememberMe)
    if (res.success && res.data) {
      setCurrentUser(res.data.user)
      setIsAuthenticated(true)
      setIsDemoAuth(Boolean(res.isDemo))
      safeSet(STORAGE_KEYS.USER, res.data.user)
      return { success: true }
    }
    return { success: false, error: res.error || 'Failed to authenticate.' }
  }

  /**
   * 1-Click Instant PM Demo Login
   */
  const demoLogin = () => {
    const res = authService.demoPMLogin()
    if (res.success && res.data) {
      setCurrentUser(res.data.user)
      setIsAuthenticated(true)
      setIsDemoAuth(true)
      safeSet(STORAGE_KEYS.USER, res.data.user)
      return res.data.user
    }
    return initialUser
  }

  /**
   * Log out and clear session state
   */
  const logout = async () => {
    await authService.logout()
    setIsAuthenticated(false)
    setIsDemoAuth(false)
    setCurrentUser(null)
    safeRemove(AUTH_TOKEN_KEY)
  }

  const updateProfile = (updates) => {
    const updated = { ...currentUser, ...updates }
    setCurrentUser(updated)
    safeSet(STORAGE_KEYS.USER, updated)
    const session = authService.getCurrentSession()
    if (session) {
      safeSet(AUTH_TOKEN_KEY, { ...session, user: updated })
    }
  }

  const forgotPassword = async (email) => {
    await new Promise(resolve => setTimeout(resolve, 600))
    return {
      success: true,
      message: `If an account exists for ${email}, password reset instructions will be provided by your administrator.`,
    }
  }

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        currentUser,
        isDemoAuth,
        register,
        login,
        demoLogin,
        logout,
        updateProfile,
        forgotPassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    const session = authService.getCurrentSession()
    return {
      currentUser: session?.user || null,
      isAuthenticated: Boolean(session),
      isDemoAuth: session?.isDemo ?? true,
      login: authService.login,
      demoLogin: authService.demoPMLogin,
      register: authService.register,
      logout: authService.logout,
      updateProfile: () => {},
      forgotPassword: () => {},
    }
  }
  return context
}

export default AuthContext
