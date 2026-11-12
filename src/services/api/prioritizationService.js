/**
 * ProductMind AI — Feature Prioritization Service
 * Real integration with FastAPI Prioritization Agent & 6-factor composite scoring engine.
 */

import { apiClient, getActiveWorkspaceId } from './apiClient'
import { API_ENDPOINTS } from './types'
import {
  calculatePriorityScore,
  getScoreBreakdown,
  rankFeatures,
  getPriorityTier,
  FACTOR_WEIGHTS,
} from '../../data/scoringFormulas'

export const prioritizationService = {
  FACTOR_WEIGHTS,

  /**
   * Run AI Prioritization Agent evaluation on workspace feature groups
   */
  async analyzePrioritization({
    workspaceId = null,
    featureGroupIds = null,
    strategicContext = null,
    weightConfig = null,
    analyticsData = null,
    usageAnalyticsEvidence = null,
    forceReanalyze = true,
  } = {}) {
    const wsId = workspaceId || getActiveWorkspaceId()
    if (!wsId) {
      throw new Error('Workspace ID is required for prioritization analysis.')
    }

    const payload = {
      workspace_id: wsId,
      force_reanalyze: Boolean(forceReanalyze),
      ...(featureGroupIds ? { feature_group_ids: featureGroupIds } : {}),
      ...(strategicContext ? { strategic_alignment_context: strategicContext } : {}),
      ...(weightConfig ? { weight_config: weightConfig } : {}),
      ...(analyticsData ? { analytics_data: analyticsData } : {}),
      ...(usageAnalyticsEvidence ? { usage_analytics_evidence: usageAnalyticsEvidence } : {}),
    }

    const response = await apiClient.post(API_ENDPOINTS.AI_PRIORITIZATION.ANALYZE, payload)
    if (!response.success) {
      throw new Error(response.error || 'Prioritization analysis failed.')
    }
    return response.data
  },

  /**
   * Fetch stored prioritization evaluation results from MongoDB
   */
  async getPrioritizationResults(workspaceId = null, params = {}) {
    const wsId = workspaceId || getActiveWorkspaceId()
    if (!wsId) return []

    const queryParams = {
      workspace_id: wsId,
      ...params,
    }

    const response = await apiClient.get(API_ENDPOINTS.AI_PRIORITIZATION.RESULTS, {
      params: queryParams,
    })
    return response.data || []
  },

  /**
   * Fetch individual prioritization result by ID
   */
  async getPrioritizationResult(resultId, workspaceId = null) {
    const wsId = workspaceId || getActiveWorkspaceId()
    const url = `/api/v1/ai/prioritization/results/${resultId}`
    const response = await apiClient.get(url, {
      params: { workspace_id: wsId },
    })
    return response.data
  },

  /**
   * Rank features using backend deterministic composite scoring
   */
  async rankFeaturesOnBackend({ workspaceId = null, featureGroupIds = null, sortBy = 'score' } = {}) {
    const wsId = workspaceId || getActiveWorkspaceId()
    const response = await apiClient.post(API_ENDPOINTS.AI_PRIORITIZATION.RANK, {
      workspace_id: wsId,
      ...(featureGroupIds ? { feature_group_ids: featureGroupIds } : {}),
      sort_by: sortBy,
    })
    return response.data
  },

  // --------------------------------------------------------------------------
  // Local fallback calculations for offline & simulation modes
  // --------------------------------------------------------------------------
  calculateScore(factors) {
    return calculatePriorityScore(factors)
  },

  getBreakdown(factors) {
    return getScoreBreakdown(factors)
  },

  getTier(score) {
    return getPriorityTier(score)
  },

  rank(featuresList) {
    return rankFeatures(featuresList)
  },

  getExplanation(feature) {
    const bd = getScoreBreakdown(feature)
    const tier = getPriorityTier(bd.totalScore)
    return {
      tier: tier.label,
      totalScore: bd.totalScore,
      summary:
        `Ranked as ${tier.label} priority with a score of ${bd.totalScore.toFixed(2)} / 10.0. ` +
        `Customer Impact contributes ${bd.customerImpactContribution.toFixed(2)} (35%), ` +
        `Urgency contributes ${bd.urgencyContribution.toFixed(2)} (30%), ` +
        `Customer Demand contributes ${bd.demandContribution.toFixed(2)} (20%), and ` +
        `Business Value contributes ${bd.businessValueContribution.toFixed(2)} (15%).`,
      formulaString: `(0.35 × ${feature.customerImpact || 5}) + (0.30 × ${feature.urgency || 5}) + (0.20 × ${feature.demand || 5}) + (0.15 × ${feature.businessValue || 5}) = ${bd.totalScore.toFixed(2)}`,
    }
  },

  async getRankedFeatures(featuresList = []) {
    try {
      const wsId = getActiveWorkspaceId()
      if (wsId) {
        const results = await this.getPrioritizationResults(wsId)
        if (Array.isArray(results) && results.length > 0) {
          return {
            success: true,
            data: results,
            isDemo: false,
            status: 200,
          }
        }
      }
    } catch {
      // Fallback
    }

    const ranked = rankFeatures(featuresList)
    return {
      success: true,
      data: ranked,
      isDemo: true,
      status: 200,
      timestamp: new Date().toISOString(),
    }
  },
}

export default prioritizationService
