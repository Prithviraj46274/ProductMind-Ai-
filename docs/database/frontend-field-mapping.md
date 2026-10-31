# ProductMind AI — Frontend-to-Database Field Mapping

This document provides a comprehensive mapping between every frontend page, UI component, data interaction, and the corresponding MongoDB models.

---

## 1. Authentication & Workspace Management

### Component: `SignInPage.jsx` & `AuthContext.jsx`
- **Models**: `User`, `Workspace`, `WorkspaceMembership`, `AuthSession`
- **Database Normalization**:
  - `User`: Global identity (`name`, `email`, `passwordHash`, `platformRole`, `avatar`, `theme`, `reducedMotion`, `lastLoginAt`).
  - `WorkspaceMembership`: Workspace role (`role`, `status`, `joinedAt`).
  - `Workspace`: Organizational container (`name`, `slug`, `plan`, `settings`).
- **Composite Session DTO (API Contract)**:
  - On `POST /api/v1/auth/login` or `GET /api/v1/auth/session`, the backend queries the user, looks up active membership in the requested/default workspace, and returns a unified session payload:
    ```json
    {
      "token": "jwt_token_string",
      "user": {
        "id": "user._id",
        "name": "Alex Rivera",
        "email": "alex.rivera@productmind.ai",
        "role": "Lead Product Architect", // from WorkspaceMembership.role
        "platformRole": "user",           // from User.platformRole
        "avatar": "AR",
        "workspaceId": "workspace._id",
        "workspaceName": "Apex SaaS Product Operations", // from Workspace.name
        "workspacePlan": "Enterprise Tier",              // from Workspace.plan
        "workspaceSlug": "apex-saas-product-operations",
        "theme": "dark",
        "reducedMotion": false
      }
    }
    ```
- **Fields Written by UI**: `email`, `password` (hashed via bcrypt on backend), `rememberMe`, `lastLoginAt`
- **Derived Values**: Session expiration timestamp (`Date.now() + 24h`), demo authentication badge
- **Future API Operations**:
  - `POST /api/v1/auth/login`
  - `POST /api/v1/auth/logout`
  - `GET /api/v1/auth/session`
  - `POST /api/v1/auth/refresh`
- **Current State**: Handled via `src/services/api/authService.js` with demo fallback when offline.

---

## 2. Customer Feedback & Triage

### Component: `FeedbackPage.jsx`
- **Model**: `FeedbackItem` & `FeedbackBatch`
- **Fields Read by UI**:
  - `id` / `_id`, `title`, `description`, `customerName` (`customer`), `companyName` (`company`), `customerEmail` (`email`), `category`, `sentiment`, `sourcePriority` (`priority`), `tags`, `feedbackDate` (`date`), `featureGroupId`, `promotedFeatureId` (`linkedFeatureId`)
- **Fields Written by UI**:
  - Creation / Edit: `title`, `description`, `customerName`, `companyName`, `category`, `sentiment`, `sourcePriority`, `tags`, `promotedFeatureId`
  - Bulk actions: `category`, `sentiment`, `sourcePriority`, deletion
- **Derived Values**:
  - Sentiment badges (color-coded)
  - Duplicate detection matches (Jaccard similarity score)
  - Smart tag suggestions
- **Future API Operations**:
  - `GET /api/v1/feedback?page=1&limit=8&category=...&sentiment=...`
  - `POST /api/v1/feedback`
  - `PUT /api/v1/feedback/:id`
  - `DELETE /api/v1/feedback/:id`
  - `POST /api/v1/feedback/batch` (CSV/JSON upload)
- **Current State**: Seed data in `src/data/seedData.js`, mutations synced to `localStorage`, API contracts defined in `src/services/api/feedbackService.js`.

---

## 3. Feature Request Aggregation & Clustering

### Component: `AggregationPage.jsx`
- **Model**: `FeatureGroup` & `FeedbackItem`
- **Fields Read by UI**:
  - `title`, `category`, `primaryTag`, `feedbackCount` (`count`), `sentimentDistribution`, `painPoints`, `status`, `promotedFeatureId`, top excerpts from linked feedback
- **Fields Written by UI**:
  - Merge groups: Updates `mergedIntoGroupId` on source, combines `painPoints`, repoints `FeedbackItem.featureGroupId`
  - Approve group: Sets `status = 'approved'`
  - Promote to feature: Creates record in `features` collection and sets `promotedFeatureId`
- **Derived Values**:
  - Sentiment bar distribution percentage
  - Top 3 feedback excerpt snippets
- **Future API Operations**:
  - `GET /api/v1/aggregation/groups`
  - `POST /api/v1/aggregation/merge`
  - `PUT /api/v1/aggregation/groups/:id/approve`
- **Current State**: Simulated via `src/services/api/aggregationService.js`.

---

## 4. Feature Prioritization Matrix

### Component: `PrioritizationPage.jsx`
- **Model**: `Feature`
- **Fields Read by UI**:
  - `name`, `description`, `customerImpact`, `urgency`, `demand`, `businessValue`, `score`, `priorityTier`, `status`, `owner`, `targetRelease`, `comments`, `aiJustification`
- **Fields Written by UI**:
  - Slider adjustments: `customerImpact` (1-10), `urgency` (1-10), `demand` (1-10), `businessValue` (1-10)
  - Status updates: `status` ('Backlog' to 'Launched')
  - Comments: New comment subdocuments
- **Derived Values**:
  - Formula: `(0.35 * Impact) + (0.30 * Urgency) + (0.20 * Demand) + (0.15 * Value)`
  - Priority Tier badge: 'Critical' (8.5-10.0), 'High' (7.0-8.49), 'Medium' (5.0-6.99), 'Low' (<5.0)
  - Mathematical contribution breakdown tooltips
- **Future API Operations**:
  - `GET /api/v1/prioritization/features`
  - `POST /api/v1/prioritization/features`
  - `PUT /api/v1/prioritization/features/:id/factors`
- **Current State**: Evaluated dynamically via `src/data/scoringFormulas.js`.

---

## 5. What-If Product Simulator

### Component: `SimulatorPage.jsx`
- **Model**: `PrioritizationScenario` & `Feature`
- **Fields Read by UI**:
  - Base feature factor scores vs simulated factors
  - Delta score comparisons
- **Fields Written by UI**:
  - `name`, `description`, `adjustedFeatures` (featureId, simulated factors)
  - "Apply to Production" button: Bulk updates live `features` collection
- **Derived Values**:
  - Before-and-after ranking shifts (e.g. +3 positions, -2 positions)
  - Recharts delta comparison chart
- **Future API Operations**:
  - `GET /api/v1/prioritization/scenarios`
  - `POST /api/v1/prioritization/scenarios`
  - `POST /api/v1/prioritization/scenarios/:id/apply`
- **Current State**: Transient slider state with save mechanism in `AppContext.jsx`.

---

## 6. PRD Specifications Studio

### Component: `PRDGeneratorPage.jsx`
- **Model**: `PRD` & `Feature`
- **Fields Read by UI**:
  - `title`, `featureId`, `version`, `status`, `author`, `updatedAt`, `sections` (all 13 sections)
- **Fields Written by UI**:
  - Textarea edits on any of the 13 sections
  - Status transitions ('Draft' -> 'In Review' -> 'Approved')
  - Title and version updates
- **Derived Values**:
  - Auto-generated content template synthesized from linked feature
  - Print & Markdown export strings
- **Future API Operations**:
  - `GET /api/v1/prds`
  - `GET /api/v1/prds/:id`
  - `POST /api/v1/prds/generate`
  - `PUT /api/v1/prds/:id`
- **Current State**: Auto-draft generator in `src/services/aiSimulationService.js` and `src/services/api/prdService.js`.

---

## 7. Strategic Roadmap & Milestones

### Component: `RoadmapPage.jsx`
- **Model**: `RoadmapItem` & `Release`
- **Fields Read by UI**:
  - `title`, `description`, `featureId`, `status`, `priority`, `owner`, `startDate`, `targetDate`, `milestone`, `progress`, `dependencies`, `notes`
- **Fields Written by UI**:
  - Dates (`startDate`, `targetDate`), status, progress slider (0-100%), milestone assignment
- **Derived Values**:
  - Timeline Gantt position bars (calculated from date spans)
  - Quarterly Kanban buckets (Q1-Q4)
- **Future API Operations**:
  - `GET /api/v1/roadmap/milestones`
  - `POST /api/v1/roadmap/milestones`
  - `PUT /api/v1/roadmap/milestones/:id`
- **Current State**: Persisted in `localStorage` under `pmai_v1_roadmap`.

---

## 8. Release Readiness Center

### Component: `ReleaseReadinessPage.jsx`
- **Model**: `Release`, `Feature`, `RoadmapItem`, `FeedbackItem`
- **Fields Read by UI**:
  - `name`, `version`, `description`, `plannedDate`, `owner`, `status`, `checklist` (`title`, `completed`, `required`), `releaseNotes`
- **Fields Written by UI**:
  - Toggle checklist item checkbox
  - Release metadata updates
- **Derived Values**:
  - `readinessPercent` (Virtual: `completedCount / totalCount * 100`)
  - `isGated` (Virtual: boolean, true if any required item is uncompleted)
  - Urgent blockers count: Filtered from `feedback_items` where `sourcePriority === 'Urgent' && sentiment === 'Negative'`
- **Future API Operations**:
  - `GET /api/v1/releases`
  - `PUT /api/v1/releases/:id/checklist/:checkId`
  - `POST /api/v1/releases`
- **Current State**: Evaluated via component logic in `ReleaseReadinessPage.jsx`.

---

## 9. Product Analytics Telemetry & Ingestion

### Component: `AnalyticsPage.jsx`
- **Model**: `AnalyticsEvent` & `AnalyticsDailyRollup`
- **Fields Read by UI**:
  - Raw and rolled-up event streams: `date`, `activeUsers`, `totalSessions`, `totalEvents`, `featureMetrics`, `funnelMetrics`, `avgSessionDuration`
- **Fields Written by UI**:
  - File upload: CSV/JSON upload parses into `AnalyticsEvent` records and computes initial `AnalyticsDailyRollup`
  - Column mapping configurations
- **Derived Values**:
  - DAU, WAU, MAU calculations
  - Funnel drop-off rates across 5 stages
  - Feature adoption percentages
- **Future API Operations**:
  - `GET /api/v1/analytics/overview?timeRange=30d`
  - `GET /api/v1/analytics/usage-trends`
  - `GET /api/v1/analytics/features`
  - `GET /api/v1/analytics/funnel`
  - `POST /api/v1/analytics/datasets/upload`
- **Current State**: Managed in `src/services/api/analyticsService.js`.

---

## 10. AI Copilot Strategy Assistant

### Component: `CopilotPage.jsx`
- **Model**: `CopilotConversation` & `CopilotMessage`
- **Fields Read by UI**:
  - `title`, `lastMessageAt`, message stream (`role`, `content`, `timestamp`, `evidence`)
- **Fields Written by UI**:
  - User query: Creates new `user` message
  - Response: Assistant reply with citation links
- **Derived Values**:
  - Dynamic evidence pills resolving to `/feedback`, `/prioritization`, `/prd-generator`, `/roadmap`, `/analytics`
- **Future API Operations**:
  - `POST /api/v1/copilot/chat`
  - `GET /api/v1/copilot/history`
- **Current State**: Handled via `src/services/api/copilotService.js`.

---

## 11. Activity History & 1-Click Reversible Undo

### Component: `ActivityHistoryPage.jsx`
- **Model**: `AuditLog`
- **Fields Read by UI**:
  - `actor`, `entityType`, `entityId`, `action`, `description`, `previousState`, `newState`, `canUndo`, `createdAt`
- **Fields Written by UI**:
  - Automatically written on every create/update/delete action across the app
  - "Reversible Undo": Restores `previousState` and sets `canUndo = false`
- **Derived Values**:
  - JSON Before/After state comparison diffs
- **Future API Operations**:
  - `GET /api/v1/history`
  - `POST /api/v1/history/:id/undo`
- **Current State**: Managed by `src/services/historyService.js`.
