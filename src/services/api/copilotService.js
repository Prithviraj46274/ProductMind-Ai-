/**
 * Product Copilot Service
 * Connects chat interface directly to FastAPI Copilot endpoints backed by MongoDB Atlas and Groq.
 * Never falls back to demo/simulation mode or fabricated responses.
 */
import { apiClient } from './apiClient'
import { API_ENDPOINTS } from './types'

const ROUTE_FALLBACKS = {
  '/features': '/feature-aggregation',
  '/prd-generator': '/prds',
}

export function normalizeEvidencePath(path) {
  if (!path || typeof path !== 'string') return '/copilot'
  return ROUTE_FALLBACKS[path] || path
}

function normalizeEvidenceList(evidence = []) {
  if (!Array.isArray(evidence)) return []
  return evidence
    .filter((ev) => ev && ev.label)
    .map((ev) => ({
      ...ev,
      path: normalizeEvidencePath(ev.path),
    }))
}

function createApiError(response, fallbackMessage) {
  const status = response?.status || 500
  let message = response?.error || fallbackMessage
  if (status === 429) {
    message =
      response?.error ||
      'Copilot is temporarily unavailable because the AI service has reached its request limit. Please try again later.'
  } else if (status === 504) {
    message = response?.error || 'Copilot request timed out. Please retry.'
  } else if (status === 401) {
    message = response?.error || 'Authentication expired. Please sign in again.'
  } else if (status === 403) {
    message = response?.error || 'You do not have access to Copilot for this workspace.'
  }
  const err = new Error(message)
  err.status = status
  return err
}

function ensureBackendReady(workspaceId) {
  if (!apiClient.isConfigured()) {
    const err = new Error('Copilot backend is not configured.')
    err.status = 503
    throw err
  }
  if (!workspaceId) {
    const err = new Error('Please select a workspace first.')
    err.status = 400
    throw err
  }
}

export const copilotService = {
  /**
   * Send a user message to the workspace-scoped Copilot API.
   */
  async sendMessage({ workspaceId, conversationId = null, message, requestId }) {
    ensureBackendReady(workspaceId)
    const trimmed = (message || '').trim()
    if (!trimmed) {
      const err = new Error('Message cannot be empty.')
      err.status = 400
      throw err
    }

    const payload = {
      workspaceId,
      message: trimmed,
      ...(conversationId ? { conversationId } : {}),
      ...(requestId ? { requestId } : {}),
    }

    const response = await apiClient.post(API_ENDPOINTS.COPILOT.CHAT, payload, {
      timeout: 65000,
    })

    if (!response?.success || response?.isDemo) {
      throw createApiError(response, 'Failed to get Copilot response.')
    }

    const data = response.data || {}
    return {
      conversation: data.conversation,
      userMessage: data.userMessage,
      assistantMessage: data.assistantMessage
        ? {
            ...data.assistantMessage,
            evidence: normalizeEvidenceList(data.assistantMessage.evidence),
          }
        : null,
      retried: Boolean(data.retried),
    }
  },

  /**
   * List active conversations for the current user in the selected workspace.
   */
  async getConversations(workspaceId, { skip = 0, limit = 20, includeArchived = false } = {}) {
    ensureBackendReady(workspaceId)
    const response = await apiClient.get(API_ENDPOINTS.COPILOT.CONVERSATIONS, {
      params: { workspaceId, skip, limit, includeArchived },
    })
    if (!response?.success || response?.isDemo) {
      throw createApiError(response, 'Failed to load Copilot conversations.')
    }
    return {
      conversations: response.data?.conversations || [],
      total: response.data?.total ?? 0,
      skip: response.data?.skip ?? skip,
      limit: response.data?.limit ?? limit,
    }
  },

  /**
   * Create an empty conversation in Atlas (does not invoke Groq).
   */
  async createConversation(workspaceId, { title = 'Strategy Session', requestId } = {}) {
    ensureBackendReady(workspaceId)
    const response = await apiClient.post(API_ENDPOINTS.COPILOT.CONVERSATIONS, {
      workspaceId,
      title,
      ...(requestId ? { requestId } : {}),
    })
    if (!response?.success || response?.isDemo) {
      throw createApiError(response, 'Failed to create conversation.')
    }
    return response.data
  },

  /**
   * Retrieve conversation metadata and paginated chronological messages.
   */
  async getConversation(conversationId, workspaceId, { skip = 0, limit = 50 } = {}) {
    ensureBackendReady(workspaceId)
    if (!conversationId) {
      const err = new Error('Conversation ID is required.')
      err.status = 400
      throw err
    }
    const response = await apiClient.get(API_ENDPOINTS.COPILOT.CONVERSATION(conversationId), {
      params: { workspaceId, skip, limit },
    })
    if (!response?.success || response?.isDemo) {
      throw createApiError(response, 'Failed to load conversation messages.')
    }
    const messages = (response.data?.messages || []).map((msg) => ({
      ...msg,
      evidence: normalizeEvidenceList(msg.evidence),
    }))
    return {
      conversation: response.data?.conversation || null,
      messages,
      total: response.data?.total ?? messages.length,
      skip: response.data?.skip ?? skip,
      limit: response.data?.limit ?? limit,
    }
  },

  async getConversationMessages(conversationId, workspaceId, options = {}) {
    return this.getConversation(conversationId, workspaceId, options)
  },

  /**
   * Archive (soft-delete) a conversation in Atlas.
   */
  async archiveConversation(conversationId, workspaceId) {
    ensureBackendReady(workspaceId)
    const response = await apiClient.delete(API_ENDPOINTS.COPILOT.ARCHIVE(conversationId), {
      params: { workspaceId },
    })
    if (!response?.success || response?.isDemo) {
      throw createApiError(response, 'Failed to archive conversation.')
    }
    return response.data
  },

  /**
   * Rename a conversation in Atlas.
   */
  async renameConversation(conversationId, workspaceId, title) {
    ensureBackendReady(workspaceId)
    const response = await apiClient.patch(API_ENDPOINTS.COPILOT.CONVERSATION(conversationId), {
      workspaceId,
      title,
    })
    if (!response?.success || response?.isDemo) {
      throw createApiError(response, 'Failed to rename conversation.')
    }
    return response.data
  },
}

export default copilotService
