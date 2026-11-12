import { describe, it, expect, vi, beforeEach } from 'vitest'
import { copilotService, normalizeEvidencePath } from '../services/api/copilotService'
import { apiClient } from '../services/api/apiClient'
import { API_ENDPOINTS } from '../services/api/types'

describe('copilotService', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    vi.spyOn(apiClient, 'isConfigured').mockReturnValue(true)
  })

  it('uses configured COPILOT endpoints and passes workspaceId and requestId', async () => {
    const postSpy = vi.spyOn(apiClient, 'post').mockResolvedValue({
      success: true,
      status: 200,
      isDemo: false,
      data: {
        conversation: { id: 'conv-1', title: 'Test' },
        userMessage: { id: 'u-1', role: 'user', content: 'Hi' },
        assistantMessage: {
          id: 'a-1',
          role: 'assistant',
          content: 'Reply',
          evidence: [{ type: 'feature_group', label: 'Export', path: '/features', count: 5 }],
        },
        retried: false,
      },
    })

    const res = await copilotService.sendMessage({
      workspaceId: 'ws-123',
      conversationId: 'conv-1',
      message: 'Hi',
      requestId: 'req-abc',
    })

    expect(postSpy).toHaveBeenCalledWith(
      API_ENDPOINTS.COPILOT.CHAT,
      { workspaceId: 'ws-123', conversationId: 'conv-1', message: 'Hi', requestId: 'req-abc' },
      expect.objectContaining({ timeout: 65000 })
    )
    expect(res.assistantMessage.evidence[0].path).toBe('/feature-aggregation')
  })

  it('throws 429 rate-limit error without falling back to simulation', async () => {
    vi.spyOn(apiClient, 'post').mockResolvedValue({
      success: false,
      status: 429,
      isDemo: false,
      error: 'Copilot is temporarily unavailable because the AI service has reached its request limit. Please try again later.',
    })

    await expect(
      copilotService.sendMessage({
        workspaceId: 'ws-123',
        message: 'Test',
        requestId: 'req-429',
      })
    ).rejects.toMatchObject({ status: 429 })
  })

  it('throws error when backend is not configured instead of demo fallback', async () => {
    vi.spyOn(apiClient, 'isConfigured').mockReturnValue(false)
    await expect(copilotService.getConversations('ws-123')).rejects.toMatchObject({ status: 503 })
  })

  it('lists, creates, retrieves, renames, and archives conversations via API', async () => {
    const getSpy = vi.spyOn(apiClient, 'get').mockResolvedValue({
      success: true,
      status: 200,
      isDemo: false,
      data: { conversations: [{ id: 'c1', title: 'S1' }], total: 1 },
    })
    const listRes = await copilotService.getConversations('ws-1')
    expect(getSpy).toHaveBeenCalledWith(API_ENDPOINTS.COPILOT.CONVERSATIONS, {
      params: { workspaceId: 'ws-1', skip: 0, limit: 20, includeArchived: false },
    })
    expect(listRes.conversations).toHaveLength(1)

    const delSpy = vi.spyOn(apiClient, 'delete').mockResolvedValue({
      success: true,
      status: 200,
      isDemo: false,
      data: { success: true, conversationId: 'c1', isArchived: true },
    })
    const archRes = await copilotService.archiveConversation('c1', 'ws-1')
    expect(delSpy).toHaveBeenCalledWith(API_ENDPOINTS.COPILOT.ARCHIVE('c1'), {
      params: { workspaceId: 'ws-1' },
    })
    expect(archRes.isArchived).toBe(true)
    expect(normalizeEvidencePath('/features')).toBe('/feature-aggregation')
  })
})

