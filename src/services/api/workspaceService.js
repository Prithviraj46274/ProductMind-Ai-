/**
 * ProductMind AI — Workspace Service
 * Handles workspace listing, creation, and selection via FastAPI endpoints.
 */

import { apiClient } from './apiClient'
import { API_ENDPOINTS } from './types'

function generateSlug(name) {
  const base = (name || '')
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
  if (!base || base.length < 3) {
    return `ws-${Math.random().toString(36).substring(2, 8)}`
  }
  return base.slice(0, 60)
}

export const workspaceService = {
  /**
   * List all workspaces accessible to the authenticated user
   */
  async listWorkspaces() {
    const response = await apiClient.get(API_ENDPOINTS.WORKSPACES.LIST)
    return response.data || []
  },

  /**
   * Get details for a specific workspace
   */
  async getWorkspace(workspaceId) {
    const url = API_ENDPOINTS.WORKSPACES.DETAIL.replace(':id', workspaceId)
    const response = await apiClient.get(url)
    return response.data
  },

  /**
   * Create a new workspace
   */
  async createWorkspace({ name, slug, settings }) {
    const finalSlug = slug ? slug.trim().toLowerCase() : generateSlug(name)
    const payload = {
      name: name.trim(),
      slug: finalSlug,
      ...(settings ? { settings } : {}),
    }
    const response = await apiClient.post(API_ENDPOINTS.WORKSPACES.LIST, payload)
    return response.data
  },

  /**
   * Update workspace settings or name
   */
  async updateWorkspace(workspaceId, data) {
    const url = API_ENDPOINTS.WORKSPACES.DETAIL.replace(':id', workspaceId)
    const response = await apiClient.patch(url, data)
    return response.data
  },
}

export default workspaceService

