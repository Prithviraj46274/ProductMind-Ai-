/**
 * ProductMind AI — AI Orchestrator Service
 * Connects to the FastAPI AI Orchestrator pipeline executing the 4-stage workflow:
 * Feedback Intelligence -> Feature Intelligence -> Prioritization -> Product Planning.
 */

import { apiClient, getActiveWorkspaceId } from './apiClient'
import { API_ENDPOINTS } from './types'

export const orchestratorService = {
  /**
   * Trigger the autonomous AI pipeline
   * @param {Object} options
   * @param {string} options.workspaceId
   * @param {'complete' | 'feedback_only' | 'features_only' | 'prioritization_only' | 'planning_only'} options.mode
   * @param {string[]} options.feedbackIds
   * @param {string[]} options.targetStages
   */
  async runPipeline({
    workspaceId = null,
    mode = 'complete',
    feedbackIds = null,
    targetStages = null,
  } = {}) {
    const wsId = workspaceId || getActiveWorkspaceId()
    if (!wsId) {
      throw new Error('Workspace ID is required to execute AI Orchestrator pipeline.')
    }

    const payload = {
      workspace_id: wsId,
      mode: mode,
      ...(feedbackIds ? { feedback_ids: feedbackIds } : {}),
      ...(targetStages ? { target_stages: targetStages } : {}),
    }

    const response = await apiClient.post(API_ENDPOINTS.AI_ORCHESTRATOR.RUN, payload)
    return response.data
  },

  /**
   * Get live execution status of an orchestrator run
   */
  async getRunStatus(runId, workspaceId = null) {
    const wsId = workspaceId || getActiveWorkspaceId()
    const url = API_ENDPOINTS.AI_ORCHESTRATOR.RUN_STATUS.replace(':id', runId)
    const response = await apiClient.get(url, {
      params: { workspace_id: wsId },
    })
    return response.data
  },
}

export default orchestratorService

