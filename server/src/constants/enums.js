/**
 * ProductMind AI — Central Domain Enums & Constants
 * Establishes consistent enums, status codes, factor weights, and validation bounds.
 */

export const UserRole = {
  LEAD_PRODUCT_ARCHITECT: 'Lead Product Architect',
  VP_PRODUCT: 'VP of Product & Strategy',
  HEAD_PRODUCT_OPS: 'Head of Product Operations',
  PRODUCT_MANAGER: 'Product Manager',
  ENGINEERING_LEAD: 'Staff Software Architect',
  VIEWER: 'Viewer',
  ADMIN: 'Workspace Admin',
}

export const UserRolesList = Object.values(UserRole)

export const MembershipStatus = {
  ACTIVE: 'active',
  INVITED: 'invited',
  INACTIVE: 'inactive',
  SUSPENDED: 'suspended',
}

export const MembershipStatusesList = Object.values(MembershipStatus)

export const WorkspacePlan = {
  STARTER: 'Starter Tier',
  PRO: 'Pro Tier',
  ENTERPRISE: 'Enterprise Tier',
}

export const WorkspacePlansList = Object.values(WorkspacePlan)

export const FeedbackSourceType = {
  MANUAL: 'manual',
  CSV: 'csv',
  JSON: 'json',
  SUPPORT_TICKET: 'support_ticket',
  GITHUB: 'github',
  JIRA: 'jira',
  SLACK: 'slack',
}

export const FeedbackSourceTypesList = Object.values(FeedbackSourceType)

export const FeedbackSentiment = {
  POSITIVE: 'Positive',
  NEUTRAL: 'Neutral',
  NEGATIVE: 'Negative',
}

export const FeedbackSentimentsList = Object.values(FeedbackSentiment)

export const FeedbackPriority = {
  URGENT: 'Urgent',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
}

export const FeedbackPrioritiesList = Object.values(FeedbackPriority)

export const FeedbackCategory = {
  PERFORMANCE: 'Performance',
  INTEGRATIONS: 'Integrations',
  USABILITY: 'Usability',
  RELIABILITY: 'Reliability',
  PRICING: 'Pricing',
  SATISFACTION: 'Satisfaction',
  FEATURE_REQUESTS: 'Feature Requests',
  GENERAL: 'General',
}

export const FeedbackCategoriesList = Object.values(FeedbackCategory)

export const FeedbackProcessingStatus = {
  RAW: 'raw',
  CLASSIFIED: 'classified',
  AGGREGATED: 'aggregated',
  ARCHIVED: 'archived',
}

export const FeedbackProcessingStatusesList = Object.values(FeedbackProcessingStatus)

export const FeatureGroupStatus = {
  SUGGESTED: 'suggested',
  APPROVED: 'approved',
  MERGED: 'merged',
  REJECTED: 'rejected',
}

export const FeatureGroupStatusesList = Object.values(FeatureGroupStatus)

export const FeatureStatus = {
  BACKLOG: 'Backlog',
  EVALUATING: 'Evaluating',
  IN_PLANNING: 'In Planning',
  IN_DEVELOPMENT: 'In Development',
  READY_FOR_RELEASE: 'Ready for Release',
  LAUNCHED: 'Launched',
}

export const FeatureStatusesList = Object.values(FeatureStatus)

export const PriorityTier = {
  CRITICAL: 'Critical',
  HIGH: 'High',
  MEDIUM: 'Medium',
  LOW: 'Low',
}

export const PriorityTiersList = Object.values(PriorityTier)

/**
 * Exact verified 4-factor prioritization weights
 * Formula: (0.35 * Impact) + (0.30 * Urgency) + (0.20 * Demand) + (0.15 * BusinessValue)
 */
export const FACTOR_WEIGHTS = {
  customerImpact: 0.35,
  urgency: 0.30,
  demand: 0.20,
  businessValue: 0.15,
}

export function calculatePriorityScore({ customerImpact = 5, urgency = 5, demand = 5, businessValue = 5 }) {
  const score = (FACTOR_WEIGHTS.customerImpact * customerImpact) +
                (FACTOR_WEIGHTS.urgency * urgency) +
                (FACTOR_WEIGHTS.demand * demand) +
                (FACTOR_WEIGHTS.businessValue * businessValue)
  return Math.round(score * 100) / 100
}

export function getPriorityTier(score) {
  if (score >= 8.5) return PriorityTier.CRITICAL
  if (score >= 7.0) return PriorityTier.HIGH
  if (score >= 5.0) return PriorityTier.MEDIUM
  return PriorityTier.LOW
}

export const PRDStatus = {
  DRAFT: 'Draft',
  IN_REVIEW: 'In Review',
  APPROVED: 'Approved',
  COMPLETED: 'Completed',
  ARCHIVED: 'Archived',
}

export const PRDStatusesList = Object.values(PRDStatus)

export const RoadmapStatus = {
  PLANNED: 'Planned',
  IN_PROGRESS: 'In Progress',
  IN_REVIEW: 'In Review',
  SHIPPED: 'Shipped',
}

export const RoadmapStatusesList = Object.values(RoadmapStatus)

export const ReleaseStatus = {
  PLANNED: 'Planned',
  IN_PROGRESS: 'In Progress',
  READY: 'Ready',
  SHIPPED: 'Shipped',
  BLOCKED: 'Blocked',
}

export const ReleaseStatusesList = Object.values(ReleaseStatus)

export const ExperimentStatus = {
  DRAFT: 'Draft',
  RUNNING: 'Running',
  COMPLETED: 'Completed',
  CANCELLED: 'Cancelled',
}

export const ExperimentStatusesList = Object.values(ExperimentStatus)

export const ExperimentConclusion = {
  ROLL_OUT: 'Roll Out',
  CONTINUE: 'Continue',
  ITERATE: 'Iterate',
  ABANDON: 'Abandon',
}

export const ExperimentConclusionsList = Object.values(ExperimentConclusion)

export const CopilotRole = {
  USER: 'user',
  ASSISTANT: 'assistant',
  SYSTEM: 'system',
}

export const CopilotRolesList = Object.values(CopilotRole)

export const AuditAction = {
  CREATED: 'created',
  UPDATED: 'updated',
  DELETED: 'deleted',
  MERGED: 'merged',
  APPROVED: 'approved',
  RESTORED: 'restored',
}

export const AuditActionsList = Object.values(AuditAction)

export const AuditEntityType = {
  FEEDBACK: 'feedback',
  FEATURE: 'feature',
  FEATURE_GROUP: 'feature_group',
  PRD: 'prd',
  ROADMAP: 'roadmap',
  RELEASE: 'release',
  EXPERIMENT: 'experiment',
  PERSONA: 'persona',
  WORKSPACE: 'workspace',
  ANALYTICS: 'analytics',
}

export const AuditEntityTypesList = Object.values(AuditEntityType)
