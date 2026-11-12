/**
 * ProductMind AI — Feature Request Aggregation Service
 * Connects to FastAPI AI Feature Intelligence Agent to cluster customer feedback,
 * aggregate demand, evaluate sentiment, and synthesize product feature proposals.
 */

import { apiClient, getActiveWorkspaceId } from './apiClient'
import { API_ENDPOINTS } from './types'

function formatGroupTitle(category, tag) {
  const cleanTag = (tag || 'General').replace(/[-_]/g, ' ')
  const capitalizedTag = cleanTag.charAt(0).toUpperCase() + cleanTag.slice(1)
  return `${capitalizedTag} (${category || 'Feature'})`
}

export const aggregationService = {
  /**
   * Run AI Feature Intelligence Agent clustering
   */
  async groupFeatures({
    workspaceId,
    feedbackIds = null,
    forceRegroup = false,
    confidenceThreshold = 0.65,
    minGroupSize = 1,
  } = {}) {
    const wsId = workspaceId || getActiveWorkspaceId()
    if (!wsId) {
      throw new Error('Workspace ID is required for feature aggregation.')
    }

    const payload = {
      workspace_id: wsId,
      ...(feedbackIds ? { feedback_ids: feedbackIds } : {}),
      force_regroup: forceRegroup,
      confidence_threshold: confidenceThreshold,
      min_group_size: minGroupSize,
    }

    const response = await apiClient.post(API_ENDPOINTS.AI_FEATURES.GROUP, payload)
    return response.data
  },

  /**
   * Fetch consolidated feature groups from backend
   */
  async getFeatureGroups(workspaceId = null, params = {}) {
    const wsId = workspaceId || getActiveWorkspaceId()
    if (!wsId) {
      return []
    }

    const queryParams = {
      workspace_id: wsId,
      ...params,
    }

    const response = await apiClient.get(API_ENDPOINTS.AI_FEATURES.GROUPS, {
      params: queryParams,
    })
    return response.data || []
  },

  /**
   * Fetch specific feature group by ID
   */
  async getFeatureGroup(groupId, workspaceId = null) {
    const wsId = workspaceId || getActiveWorkspaceId()
    const url = API_ENDPOINTS.AI_FEATURES.GROUP_BY_ID.replace(':id', groupId)
    const response = await apiClient.get(url, {
      params: { workspace_id: wsId },
    })
    return response.data
  },

  /**
   * Detect duplicates among feedback items using AI
   */
  async detectDuplicates({ workspaceId, feedbackIds, targetFeedbackId = null }) {
    const wsId = workspaceId || getActiveWorkspaceId()
    const response = await apiClient.post(API_ENDPOINTS.AI_FEATURES.DETECT_DUPLICATES, {
      workspace_id: wsId,
      feedback_ids: feedbackIds,
      ...(targetFeedbackId ? { target_feedback_id: targetFeedbackId } : {}),
    })
    return response.data
  },

  /**
   * Backward-compatible local clustering fallback for demo/offline states
   */
  generateAggregatedGroups(feedbackList = [], featuresList = []) {
    if (!Array.isArray(feedbackList) || feedbackList.length === 0) {
      return []
    }

    const clusterMap = {}
    feedbackList.forEach((item) => {
      const primaryTag = (item.tags && item.tags[0]) || item.category || 'General'
      const key = `${item.category}__${primaryTag.toLowerCase()}`

      if (!clusterMap[key]) {
        clusterMap[key] = {
          id: `grp-${key.replace(/[^a-z0-9]/gi, '-').toLowerCase()}`,
          title: formatGroupTitle(item.category, primaryTag),
          category: item.category,
          primaryTag,
          feedbackItems: [],
          sentimentDistribution: { Positive: 0, Neutral: 0, Negative: 0 },
          painPoints: [],
          status: 'suggested',
          promotedFeatureId: item.linkedFeatureId || null,
        }
      }

      clusterMap[key].feedbackItems.push(item)
      if (item.sentiment && clusterMap[key].sentimentDistribution[item.sentiment] !== undefined) {
        clusterMap[key].sentimentDistribution[item.sentiment]++
      }
      if (item.sentiment === 'Negative' && item.title) {
        if (!clusterMap[key].painPoints.includes(item.title)) {
          clusterMap[key].painPoints.push(item.title)
        }
      }
    })

    return Object.values(clusterMap)
      .map((group) => {
        const count = group.feedbackItems.length
        const excerpts = group.feedbackItems.slice(0, 3).map((f) => ({
          id: f.id,
          title: f.title,
          customer: f.customer,
          company: f.company,
          sentiment: f.sentiment,
          snippet: (f.description || f.title).slice(0, 100) + '...',
        }))

        const existingFeature = featuresList.find(
          (feat) =>
            feat.id === group.promotedFeatureId ||
            group.feedbackItems.some((fi) => fi.linkedFeatureId === feat.id)
        )

        return {
          ...group,
          count,
          excerpts,
          isPromoted: Boolean(existingFeature),
          promotedFeatureName: existingFeature?.name || null,
          promotedFeatureScore: existingFeature?.score || null,
          painPoints: group.painPoints.slice(0, 4),
        }
      })
      .sort((a, b) => b.count - a.count)
  },

  /**
   * Compatibility wrapper
   */
  async getGroups(feedbackList = [], featuresList = []) {
    try {
      const wsId = getActiveWorkspaceId()
      if (wsId) {
        const groups = await this.getFeatureGroups(wsId)
        if (Array.isArray(groups) && groups.length > 0) {
          return {
            success: true,
            data: groups,
            isDemo: false,
            status: 200,
          }
        }
      }
    } catch {
      // Fallback to local aggregation
    }

    const groups = this.generateAggregatedGroups(feedbackList, featuresList)
    return {
      success: true,
      data: groups,
      isDemo: true,
      status: 200,
      timestamp: new Date().toISOString(),
    }
  },
}

export default aggregationService
