/**
 * ProductMind AI — Customer Feedback Service
 * Real FastAPI & MongoDB integration for feedback ingestion and AI Feedback Intelligence analysis.
 */
import { apiClient, getActiveWorkspaceId } from './apiClient'
import { API_ENDPOINTS } from './types'

export const feedbackService = {
  /**
   * Fetch feedback items for the active workspace
   */
  async getFeedbackList(params = {}) {
    const workspaceId = params.workspaceId || getActiveWorkspaceId()
    const queryParams = { ...params }
    if (workspaceId) {
      queryParams.workspaceId = workspaceId
    }

    const response = await apiClient.get(API_ENDPOINTS.FEEDBACK.LIST, {
      params: queryParams,
    })
    return response.data
  },

  /**
   * Create a manual feedback item in the active workspace
   */
  async createFeedback(feedbackItem) {
    const workspaceId = feedbackItem.workspaceId || getActiveWorkspaceId()
    if (!workspaceId) {
      throw new Error('No active workspace selected.')
    }

    const externalId =
      feedbackItem.external_id ||
      feedbackItem.externalId ||
      `fb-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`

    // Map UI model to backend FeedbackItemCreate schema
    const payload = {
      title: feedbackItem.title,
      description: feedbackItem.description,
      source_type: 'manual',
      external_id: externalId,
      customer_name: feedbackItem.customer || feedbackItem.customer_name || 'Anonymous Customer',
      customer_email: feedbackItem.customer_email || 'feedback@example.com',
      company_name: feedbackItem.company || feedbackItem.company_name || 'Independent Client',
      tags: feedbackItem.tags || [],
      ...(feedbackItem.category && feedbackItem.category !== 'All' ? { category: feedbackItem.category.toLowerCase().replace(/ /g, '_') } : {}),
      ...(feedbackItem.sentiment && feedbackItem.sentiment !== 'All' ? { sentiment: feedbackItem.sentiment.toLowerCase() } : {}),
      ...(feedbackItem.priority && feedbackItem.priority !== 'All' ? { source_priority: feedbackItem.priority.toLowerCase() } : {}),
    }

    const response = await apiClient.post(
      `${API_ENDPOINTS.FEEDBACK.CREATE}?workspaceId=${encodeURIComponent(workspaceId)}`,
      payload,
      {
        headers: {
          'Idempotency-Key': externalId,
        },
      }
    )
    return response.data
  },

  /**
   * Update feedback record
   */
  async updateFeedback(id, updates) {
    const url = API_ENDPOINTS.FEEDBACK.UPDATE(id)
    const response = await apiClient.put(url, updates)
    return response.data
  },

  /**
   * Delete feedback record
   */
  async deleteFeedback(id) {
    const url = API_ENDPOINTS.FEEDBACK.DELETE(id)
    const response = await apiClient.delete(url)
    return response.data
  },

  /**
   * Run real AI Feedback Intelligence Agent analysis on an item
   */
  async analyzeFeedback(feedbackId, forceReanalyze = false) {
    const url = API_ENDPOINTS.AI_FEEDBACK.ANALYZE.replace(':id', feedbackId)
    const response = await apiClient.post(url, { force_reanalyze: forceReanalyze })
    return response.data
  },

  /**
   * Retrieve cached AI analysis for a feedback item without consuming LLM quota
   */
  async getFeedbackAnalysis(feedbackId) {
    const url = `/api/v1/ai/feedback/${feedbackId}/analysis`
    const response = await apiClient.get(url)
    return response.data
  },

  /**
   * Batch analyze up to 10 feedback items
   */
  async batchAnalyze(feedbackIds, forceReanalyze = false) {
    const response = await apiClient.post('/api/v1/ai/feedback/analyze-batch', {
      feedback_ids: feedbackIds,
      force_reanalyze: forceReanalyze,
    })
    return response.data
  },
}

export default feedbackService
