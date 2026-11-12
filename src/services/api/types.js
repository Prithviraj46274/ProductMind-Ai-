/**
 * ProductMind AI — Centralized API Types and Contracts
 * Defines standard schemas, endpoints, and request/response envelopes
 * for frontend-to-backend integration.
 */

/**
 * Standard API Response Envelope
 * @template T
 * @typedef {Object} ApiResponse
 * @property {boolean} success - Whether the request succeeded
 * @property {T} [data] - Response payload if successful
 * @property {string} [error] - Error message if failed
 * @property {number} status - HTTP status code
 * @property {boolean} isDemo - Flag indicating if response was resolved via frontend demo fallback
 * @property {string} [timestamp] - ISO timestamp of response
 */

/**
 * Configured API Endpoints matching FastAPI backend registered routes.
 */
export const API_ENDPOINTS = {
  // Authentication & Sessions
  AUTH: {
    REGISTER: '/api/v1/auth/register',
    LOGIN: '/api/v1/auth/login',
    LOGOUT: '/api/v1/auth/logout',
    SESSION: '/api/v1/auth/session',
    REFRESH: '/api/v1/auth/refresh',
    ME: '/api/v1/auth/me',
  },

  // Multi-Tenant Workspaces
  WORKSPACES: {
    LIST: '/api/v1/workspaces',
    CREATE: '/api/v1/workspaces',
    DETAIL: (id) => `/api/v1/workspaces/${id}`,
    MEMBERS: (id) => `/api/v1/workspaces/${id}/members`,
  },

  // Customer Feedback Ingestion & Retrieval
  FEEDBACK: {
    LIST: '/api/v1/feedback',
    CREATE: '/api/v1/feedback',
    DETAIL: (id) => `/api/v1/feedback/${id}`,
    BATCH_IMPORT: '/api/v1/feedback/batch',
    BATCH_STATUS: (batchId) => `/api/v1/feedback/batch/${batchId}`,
  },

  // AI Feedback Intelligence Agent
  AI_FEEDBACK: {
    ANALYZE: (id) => `/api/v1/ai/feedback/${id}/analyze`,
    ANALYSIS: (id) => `/api/v1/ai/feedback/${id}/analysis`,
    BATCH_ANALYZE: '/api/v1/ai/feedback/analyze-batch',
  },

  // AI Feature Intelligence Agent (Clustering & Deduplication)
  AI_FEATURES: {
    GROUP: '/api/v1/ai/features/group',
    GROUPS: '/api/v1/ai/features/groups',
    GROUP_DETAIL: (id) => `/api/v1/ai/features/groups/${id}`,
    DUPLICATES: '/api/v1/ai/features/detect-duplicates',
  },

  // AI Prioritization Agent (6-Factor Scoring Engine)
  AI_PRIORITIZATION: {
    ANALYZE: '/api/v1/ai/prioritization/analyze',
    RESULTS: '/api/v1/ai/prioritization/results',
    RESULT_DETAIL: (id) => `/api/v1/ai/prioritization/results/${id}`,
    RANK: '/api/v1/ai/prioritization/rank',
  },

  // AI Product Planning Agent (PRDs & User Stories)
  AI_PLANNING: {
    GENERATE: '/api/v1/ai/planning/generate',
    GENERATE_PRD: '/api/v1/ai/planning/generate-prd',
    GENERATE_STORIES: '/api/v1/ai/planning/generate-user-stories',
    LIST: '/api/v1/ai/planning/',
    DETAIL: (id) => `/api/v1/ai/planning/${id}`,
    REVIEW: (id) => `/api/v1/ai/planning/${id}/review`,
  },

  // AI Orchestrator Pipeline
  AI_ORCHESTRATOR: {
    RUN: '/api/v1/orchestrator/run',
    STATUS: (runId) => `/api/v1/orchestrator/runs/${runId}`,
    HEALTH: '/api/v1/orchestrator/health',
  },

  // Product Analytics
  ANALYTICS: {
    OVERVIEW: '/api/v1/analytics/overview',
    USAGE_TRENDS: '/api/v1/analytics/usage-trends',
    FEATURE_ADOPTION: '/api/v1/analytics/features',
    FUNNEL: '/api/v1/analytics/funnel',
    UPLOAD_DATASET: '/api/v1/analytics/datasets/upload',
    UPLOAD_BATCH: '/api/v1/analytics/events/batch',
    LIST_DATASETS: '/api/v1/analytics/datasets',
    DATASET_DETAIL: (batchId) => `/api/v1/analytics/datasets/${batchId}`,
  },

  // Conversational Product Copilot
  COPILOT: {
    CHAT: '/api/v1/copilot/chat',
    CONVERSATIONS: '/api/v1/copilot/conversations',
    CONVERSATION: (conversationId) => `/api/v1/copilot/conversations/${conversationId}`,
    ARCHIVE: (conversationId) => `/api/v1/copilot/conversations/${conversationId}`,
  },
}
