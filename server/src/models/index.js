/**
 * ProductMind AI — Central Model Registry & Exports
 * Exports all Mongoose schemas and models covering all ten official product modules.
 */

// Module 1: Auth & Workspace
export { User } from './auth/User.model.js'
export { Workspace } from './auth/Workspace.model.js'
export { WorkspaceMembership } from './auth/WorkspaceMembership.model.js'
export { AuthSession } from './auth/AuthSession.model.js'

// Module 2: Feedback & Ingestion
export { FeedbackBatch } from './feedback/FeedbackBatch.model.js'
export { FeedbackItem } from './feedback/FeedbackItem.model.js'

// Module 3: Product Analytics
export { AnalyticsBatch } from './analytics/AnalyticsBatch.model.js'
export { AnalyticsEvent } from './analytics/AnalyticsEvent.model.js'
export { AnalyticsDailyRollup } from './analytics/AnalyticsDailyRollup.model.js'

// Modules 4 & 5: Intelligence & Aggregation
export { FeatureGroup } from './intelligence/FeatureGroup.model.js'
export { CustomerPersona } from './intelligence/CustomerPersona.model.js'
export { CompetitorIntel } from './intelligence/CompetitorIntel.model.js'

// Modules 6, 7 & 8: Planning, Prioritization, PRD & Roadmap
export { Feature } from './planning/Feature.model.js'
export { PrioritizationScenario } from './planning/PrioritizationScenario.model.js'
export { PRD } from './planning/PRD.model.js'
export { RoadmapItem } from './planning/RoadmapItem.model.js'
export { Release } from './planning/Release.model.js'
export { ProductExperiment } from './planning/ProductExperiment.model.js'
export { CustomerJourney } from './planning/CustomerJourney.model.js'

// Module 9: AI Copilot
export { CopilotConversation } from './copilot/CopilotConversation.model.js'
export { CopilotMessage } from './copilot/CopilotMessage.model.js'

// Module 10: Reporting & Audit
export { SavedReport } from './reporting/SavedReport.model.js'
export { AuditLog } from './audit/AuditLog.model.js'
