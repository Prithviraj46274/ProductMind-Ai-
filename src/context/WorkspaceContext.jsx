import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { workspaceService } from '../services/api/workspaceService'
import { getActiveWorkspaceId, setActiveWorkspaceId, isBackendConfigured, getAuthToken } from '../services/api/apiClient'
import { useAuth } from './AuthContext'

const WorkspaceContext = createContext(null)

const DEFAULT_DEMO_WORKSPACE = {
  id: 'apex-saas-product-operations',
  name: 'Apex Product Ops',
  slug: 'apex-saas-product-operations',
  plan: 'enterprise',
}

export function WorkspaceProvider({ children }) {
  const auth = useAuth()
  const isAuthenticated = auth?.isAuthenticated ?? false
  const currentUser = auth?.currentUser ?? null
  const [workspaces, setWorkspaces] = useState([])
  const [currentWorkspace, setCurrentWorkspace] = useState(null)
  const [isLoadingWorkspaces, setIsLoadingWorkspaces] = useState(false)
  const [workspaceError, setWorkspaceError] = useState(null)

  const fetchWorkspaces = useCallback(async () => {
    if (!isAuthenticated) {
      setWorkspaces([])
      setCurrentWorkspace(null)
      return
    }

    const token = getAuthToken()
    if (!isBackendConfigured() || !token || token.startsWith('mock_')) {
      setWorkspaces([DEFAULT_DEMO_WORKSPACE])
      setCurrentWorkspace(DEFAULT_DEMO_WORKSPACE)
      setActiveWorkspaceId(DEFAULT_DEMO_WORKSPACE.id)
      return
    }

    setIsLoadingWorkspaces(true)
    setWorkspaceError(null)

    try {
      const list = await workspaceService.listWorkspaces()
      setWorkspaces(list)

      const storedId = getActiveWorkspaceId()
      let selected = null

      if (storedId && list.length > 0) {
        selected = list.find((w) => w.id === storedId || w.slug === storedId)
      }

      if (!selected && list.length > 0) {
        selected = list[0]
      }

      if (selected) {
        setCurrentWorkspace(selected)
        setActiveWorkspaceId(selected.id)
      } else {
        setCurrentWorkspace(null)
      }
    } catch (err) {
      console.warn('Could not fetch workspaces from backend:', err)
      setWorkspaceError(err?.message || 'Failed to load workspaces')
      // Fallback to default if no workspaces loaded
      if (!currentWorkspace) {
        setCurrentWorkspace(DEFAULT_DEMO_WORKSPACE)
        setActiveWorkspaceId(DEFAULT_DEMO_WORKSPACE.id)
      }
    } finally {
      setIsLoadingWorkspaces(false)
    }
  }, [isAuthenticated])

  useEffect(() => {
    fetchWorkspaces()
  }, [fetchWorkspaces])

  const selectWorkspace = useCallback((workspaceId) => {
    const found = workspaces.find((w) => w.id === workspaceId || w.slug === workspaceId)
    if (found) {
      setCurrentWorkspace(found)
      setActiveWorkspaceId(found.id)
    }
  }, [workspaces])

  const createWorkspace = useCallback(async ({ name, slug, settings }) => {
    setIsLoadingWorkspaces(true)
    try {
      const created = await workspaceService.createWorkspace({ name, slug, settings })
      setWorkspaces((prev) => [...prev, created])
      setCurrentWorkspace(created)
      setActiveWorkspaceId(created.id)
      return { success: true, workspace: created }
    } catch (err) {
      const msg = err?.message || 'Failed to create workspace'
      setWorkspaceError(msg)
      return { success: false, error: msg }
    } finally {
      setIsLoadingWorkspaces(false)
    }
  }, [])

  return (
    <WorkspaceContext.Provider
      value={{
        workspaces,
        currentWorkspace,
        currentWorkspaceId: currentWorkspace?.id || null,
        isLoadingWorkspaces,
        workspaceError,
        selectWorkspace,
        createWorkspace,
        refreshWorkspaces: fetchWorkspaces,
      }}
    >
      {children}
    </WorkspaceContext.Provider>
  )
}

export function useWorkspace() {
  const context = useContext(WorkspaceContext)
  if (!context) {
    return {
      workspaces: [DEFAULT_DEMO_WORKSPACE],
      currentWorkspace: DEFAULT_DEMO_WORKSPACE,
      currentWorkspaceId: DEFAULT_DEMO_WORKSPACE.id,
      isLoadingWorkspaces: false,
      workspaceError: null,
      selectWorkspace: () => {},
      createWorkspace: async () => ({ success: true }),
      refreshWorkspaces: () => {},
    }
  }
  return context
}

