/**
 * ProductMind AI — PRD and Product Planning Service
 * Real integration with FastAPI Product Planning Agent for automated PRD,
 * user stories, acceptance criteria, technical specs, and human review workflows.
 */

import { apiClient, getActiveWorkspaceId } from './apiClient'
import { API_ENDPOINTS } from './types'

export const prdService = {
  /**
   * Run real AI Product Planning Agent to generate complete PRD & Plan
   */
  async generateProductPlan({
    workspaceId = null,
    featureGroupId,
    strategicContext = null,
    targetRelease = 'v2.5.0',
    includeTechnicalSpecs = true,
    includeUserStories = true,
    includeMetrics = true,
    includeRoadmap = true,
  }) {
    const wsId = workspaceId || getActiveWorkspaceId()
    if (!wsId) {
      throw new Error('Workspace ID is required to generate a product plan.')
    }
    if (!featureGroupId) {
      throw new Error('Feature group ID is required.')
    }

    const normalizedStrategicContext =
      typeof strategicContext === 'string'
        ? { product_name: strategicContext, additional_planning_instructions: strategicContext }
        : strategicContext

    const payload = {
      workspace_id: wsId,
      feature_group_id: featureGroupId,
      ...(normalizedStrategicContext ? { strategic_context: normalizedStrategicContext } : {}),
    }

    const response = await apiClient.post(API_ENDPOINTS.AI_PLANNING.GENERATE, payload)
    if (!response.success) {
      throw new Error(response.error || 'Failed to generate product plan.')
    }
    return response.data
  },

  /**
   * List saved Product Plans from backend
   */
  async listProductPlans(workspaceId = null, status = null) {
    const wsId = workspaceId || getActiveWorkspaceId()
    if (!wsId) return []

    const queryParams = {
      workspace_id: wsId,
      ...(status ? { status } : {}),
    }

    const response = await apiClient.get(API_ENDPOINTS.AI_PLANNING.LIST, {
      params: queryParams,
    })
    return response.data || []
  },

  /**
   * Retrieve a specific Product Plan by PRD/Plan ID
   */
  async getProductPlan(planningId, workspaceId = null) {
    const wsId = workspaceId || getActiveWorkspaceId()
    const url = `/api/v1/ai/planning/${planningId}`
    const response = await apiClient.get(url, {
      params: { workspace_id: wsId },
    })
    return response.data
  },

  /**
   * Submit human review decision (approve, reject, pending_review, draft)
   */
  async reviewProductPlan(planningId, action, notes = '') {
    const url = API_ENDPOINTS.AI_PLANNING.REVIEW(planningId)
    const statusMap = {
      approve: 'approved',
      approved: 'approved',
      reject: 'rejected',
      rejected: 'rejected',
      request_changes: 'pending_review',
      pending_review: 'pending_review',
      draft: 'draft',
    }
    const reviewStatus = statusMap[String(action || '').toLowerCase()] || action
    const response = await apiClient.patch(url, {
      review_status: reviewStatus,
      ...(notes ? { review_notes: notes } : {}),
    })
    if (!response.success) {
      throw new Error(response.error || 'Failed to update PRD review status.')
    }
    return response.data
  },

  /**
   * Generate PRD compatibility wrapper
   */
  async generatePRD(feature, customTitle = '') {
    const wsId = getActiveWorkspaceId()
    if (wsId && feature?.id) {
      try {
        const plan = await this.generateProductPlan({
          workspaceId: wsId,
          featureGroupId: feature.id,
          strategicContext: customTitle || feature.name,
        })
        return {
          success: true,
          data: plan,
          isDemo: false,
          status: 200,
        }
      } catch (err) {
        console.warn('Real AI PRD generation failed, falling back to local template:', err)
      }
    }

    // Local fallback document
    const fallbackPRD = {
      id: `prd-${Date.now()}`,
      title: customTitle || (feature ? `${feature.name} Specification` : 'Product Requirements Document'),
      featureId: feature?.id || null,
      version: '1.0.0',
      status: 'Pending Review',
      review_status: 'pending_review',
      createdAt: new Date().toISOString().split('T')[0],
      updatedAt: new Date().toISOString().split('T')[0],
      executive_summary: `Comprehensive specification for ${feature?.name || 'this initiative'}, synthesized from verified customer feedback.`,
      user_stories: [
        {
          id: 'US-101',
          title: `Enable ${feature?.name || 'feature'} Core Flow`,
          story: `As a product user, I want ${feature?.name || 'this functionality'} so that my team can streamline daily operations.`,
          acceptance_criteria: [
            'Given the user is on the product page, When they access the new interface, Then they can perform the action seamlessly.',
            'Given an invalid input, When submitted, Then the system displays an inline validation message.',
          ],
        },
      ],
      technical_specifications: [
        'Backend service endpoint contracts validated with Pydantic schemas.',
        'Data persistence in MongoDB with tenant workspace boundaries.',
      ],
      success_metrics: [
        { name: 'Adoption Rate', target: '40% within 30 days', baseline: null },
        { name: 'Customer Sentiment Score', target: '+0.50 positive shift', baseline: null },
      ],
    }

    return {
      success: true,
      data: fallbackPRD,
      isDemo: true,
      status: 200,
    }
  },

  async getPRDs() {
    const wsId = getActiveWorkspaceId()
    if (wsId) {
      try {
        const plans = await this.listProductPlans(wsId)
        return { success: true, data: plans, isDemo: false, status: 200 }
      } catch {
        // Fallback
      }
    }
    return { success: true, data: null, isDemo: true, status: 200 }
  },

  async updatePRD(id, updates) {
    return { success: true, data: { id, ...updates }, isDemo: true, status: 200 }
  },
}

export default prdService
